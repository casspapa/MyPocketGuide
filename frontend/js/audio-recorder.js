/**
 * Audio Recorder Worklet — with resampling to 16kHz
 *
 * FIX: On mobile browsers (especially Chrome Android), AudioContext({ sampleRate: 16000 })
 * is a *hint*, not a guarantee. The browser may create the context at the device's
 * native rate (typically 48000Hz). Previously the code sent this higher-rate audio
 * labelled as 16kHz, causing Gemini to reject it with:
 *   "error when processing input audio, please check if the inputaudio is in
 *    valid format: 16khz s16le pcm, mono channel"
 *
 * This version detects the actual sample rate and resamples to 16kHz client-side
 * before sending. The resampling adds ~5ms per chunk — imperceptible for speech.
 */

let micStream;

const TARGET_SAMPLE_RATE = 16000;

export async function startAudioRecorderWorklet(audioRecorderHandler) {
  // Request 16kHz — browser may or may not honour this
  const audioRecorderContext = new AudioContext({ sampleRate: TARGET_SAMPLE_RATE });
  const actualRate = audioRecorderContext.sampleRate;

  const needsResample = actualRate !== TARGET_SAMPLE_RATE;

  // Log clearly so we can verify on mobile
  if (needsResample) {
    console.warn(
      `[AudioRecorder] Browser ignored 16kHz request — actual rate: ${actualRate}Hz. Will resample to ${TARGET_SAMPLE_RATE}Hz.`
    );
  } else {
    console.log(`[AudioRecorder] AudioContext running at ${actualRate}Hz ✓`);
  }

  // Load the AudioWorklet module
  const workletURL = new URL("./pcm-recorder-processor.js", import.meta.url);
  await audioRecorderContext.audioWorklet.addModule(workletURL);

  // Request access to the microphone — mono channel as required by Live API
  // noiseSuppression + echoCancellation + autoGainControl = browser-level
  // audio filtering that reduces background noise before it reaches the worklet.
  // These are WebRTC constraints supported by Chrome, Firefox, Safari, and Edge.
  micStream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      sampleRate: TARGET_SAMPLE_RATE,
      noiseSuppression: true,
      echoCancellation: true,
      autoGainControl: true,
    },
  });
  const source = audioRecorderContext.createMediaStreamSource(micStream);

  // Create an AudioWorkletNode that uses the PCMProcessor
  const audioRecorderNode = new AudioWorkletNode(
    audioRecorderContext,
    "pcm-recorder-processor"
  );

  // Connect the microphone source to the worklet
  source.connect(audioRecorderNode);

  audioRecorderNode.port.onmessage = (event) => {
    let float32Data = event.data;

    // Resample if the AudioContext is running at a different rate
    if (needsResample) {
      float32Data = resampleLinear(float32Data, actualRate, TARGET_SAMPLE_RATE);
    }

    // Convert to 16-bit PCM and send
    const pcmData = convertFloat32ToPCM(float32Data);
    audioRecorderHandler(pcmData);
  };

  return [audioRecorderNode, audioRecorderContext, micStream];
}

/**
 * Stop the microphone.
 */
export function stopMicrophone(micStream) {
  micStream.getTracks().forEach((track) => track.stop());
  console.log("stopMicrophone(): Microphone stopped.");
}

/**
 * Resample Float32 audio from one sample rate to another using linear interpolation.
 * Lightweight (~5ms per chunk) and perfectly adequate for speech audio.
 *
 * For example, resampling from 48000 → 16000 (ratio 3) means every 3 input
 * samples become 1 output sample, with smooth interpolation between them.
 *
 * @param {Float32Array} inputData  - Source audio samples
 * @param {number}       fromRate   - Source sample rate (e.g. 48000)
 * @param {number}       toRate     - Target sample rate (e.g. 16000)
 * @returns {Float32Array} Resampled audio
 */
function resampleLinear(inputData, fromRate, toRate) {
  if (fromRate === toRate) return inputData;

  const ratio = fromRate / toRate;
  const outputLength = Math.round(inputData.length / ratio);
  const output = new Float32Array(outputLength);

  for (let i = 0; i < outputLength; i++) {
    const srcIndex = i * ratio;
    const srcFloor = Math.floor(srcIndex);
    const srcCeil = Math.min(srcFloor + 1, inputData.length - 1);
    const frac = srcIndex - srcFloor;

    // Linear interpolation between adjacent samples
    output[i] = inputData[srcFloor] * (1 - frac) + inputData[srcCeil] * frac;
  }

  return output;
}

/**
 * Convert Float32 samples to 16-bit PCM (s16le).
 * Clamps input to [-1, 1] before scaling to prevent Int16 overflow.
 */
function convertFloat32ToPCM(inputData) {
  const pcm16 = new Int16Array(inputData.length);
  for (let i = 0; i < inputData.length; i++) {
    // Clamp to [-1, 1] — Web Audio can occasionally exceed this range
    const s = Math.max(-1, Math.min(1, inputData[i]));
    // Symmetric scaling: negative maps to [-32768, 0], positive to [0, 32767]
    pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return pcm16.buffer;
}