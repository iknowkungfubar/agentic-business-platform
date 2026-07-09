import { useState, useEffect, useRef, useCallback } from 'react';
import { useAppStore } from '../store/useChatStore';
import { Mic, MicOff, PhoneOff, Loader2 } from 'lucide-react';

const WS_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/^http/, 'ws');

export function VoiceAgent() {
  const token = useAppStore((s) => s.token);
  const [connected, setConnected] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [transcript, setTranscript] = useState('');
  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const animFrameRef = useRef<number>(0);

  // Connect WebRTC signaling
  const connect = useCallback(() => {
    if (!token) return;
    const ws = new WebSocket(`${WS_BASE}/ws/voice?token=${token}`);

    ws.onopen = () => {
      setConnected(true);
      // Create SDP offer
      ws.send(JSON.stringify({
        type: 'offer',
        sdp: 'webRTC session request',
      }));
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'transcript') {
          setTranscript(data.text);
        }
      } catch {
        // Ignore non-JSON messages
      }
    };

    ws.onclose = () => {
      setConnected(false);
      setIsSpeaking(false);
    };

    wsRef.current = ws;
  }, [token]);

  const disconnect = useCallback(() => {
    wsRef.current?.close();
    mediaStreamRef.current?.getTracks().forEach((t) => t.stop());
    audioContextRef.current?.close();
    cancelAnimationFrame(animFrameRef.current);
    setConnected(false);
    setIsSpeaking(false);
  }, []);

  // Start audio capture and waveform visualization
  const startListening = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;

      const audioContext = new AudioContext();
      audioContextRef.current = audioContext;

      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);

      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);
      const canvas = canvasRef.current;

      setIsSpeaking(true);

      const draw = () => {
        if (!canvas) return;
        animFrameRef.current = requestAnimationFrame(draw);

        analyser.getByteFrequencyData(dataArray);
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        ctx.fillStyle = '#0f172a';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        const barWidth = (canvas.width / bufferLength) * 2.5;
        let x = 0;

        for (let i = 0; i < bufferLength; i++) {
          const barHeight = (dataArray[i] / 255) * canvas.height;
          const gradient = ctx.createLinearGradient(0, canvas.height, 0, canvas.height - barHeight);
          gradient.addColorStop(0, '#10b981');
          gradient.addColorStop(1, '#34d399');
          ctx.fillStyle = gradient;
          ctx.fillRect(x, canvas.height - barHeight, barWidth, barHeight);
          x += barWidth + 1;
        }
      };

      draw();
    } catch (err) {
      console.error('Microphone access denied:', err);
    }
  };

  const stopListening = () => {
    mediaStreamRef.current?.getTracks().forEach((t) => t.stop());
    audioContextRef.current?.close();
    cancelAnimationFrame(animFrameRef.current);
    setIsSpeaking(false);
  };

  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return (
    <div className="flex flex-col items-center justify-center h-full bg-slate-900 text-slate-100 p-8">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold mb-2">Voice AI Agent</h2>
        <p className="text-slate-400 text-sm">
          {connected ? 'Connected — start speaking' : 'Connect to enable voice'}
        </p>
      </div>

      {/* Waveform visualizer */}
      <div className="w-full max-w-lg mb-8">
        <canvas
          ref={canvasRef}
          width={500}
          height={120}
          className="w-full h-32 rounded-xl bg-slate-950 border border-slate-700"
          aria-label="Voice waveform visualizer"
        />
      </div>

      {/* Live transcript */}
      {transcript && (
        <div className="w-full max-w-lg mb-6 p-4 bg-slate-800 rounded-xl border border-slate-700">
          <p className="text-xs text-slate-500 mb-1">Transcript</p>
          <p className="text-sm text-slate-200">{transcript}</p>
        </div>
      )}

      {/* Controls */}
      <div className="flex gap-4">
        {!connected ? (
          <button
            onClick={connect}
            className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white px-6 py-3 rounded-xl font-medium transition-colors"
            aria-label="Connect voice"
          >
            <Mic size={20} /> Connect
          </button>
        ) : (
          <>
            {isSpeaking ? (
              <button
                onClick={stopListening}
                className="flex items-center gap-2 bg-red-600 hover:bg-red-500 text-white px-6 py-3 rounded-xl font-medium transition-colors"
                aria-label="Stop listening"
              >
                <MicOff size={20} /> Stop
              </button>
            ) : (
              <button
                onClick={startListening}
                className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white px-6 py-3 rounded-xl font-medium transition-colors"
                aria-label="Start listening"
              >
                <Loader2 size={20} className="animate-pulse" /> Speak
              </button>
            )}
            <button
              onClick={disconnect}
              className="flex items-center gap-2 bg-slate-700 hover:bg-slate-600 text-white px-6 py-3 rounded-xl font-medium transition-colors"
              aria-label="Disconnect"
            >
              <PhoneOff size={20} /> Disconnect
            </button>
          </>
        )}
      </div>
    </div>
  );
}
