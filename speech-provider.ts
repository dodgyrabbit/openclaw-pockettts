import type { SpeechProviderPlugin } from "openclaw/plugin-sdk/speech";

type PocketTtsConfig = {
  baseUrl: string;
  endpointPath: string;
  timeoutMs: number;
  defaultVoice?: string;
  responseFormat: "wav" | "pcm";
};

function extractPocketTtsConfigFromGatewayConfig(cfg: unknown): Record<string, unknown> | undefined {
  const root = asObject(cfg);
  const messages = asObject(root.messages);
  const tts = asObject(messages.tts);
  const providers = asObject(tts.providers);
  const resolved = asObject(providers.pockettts);
  return Object.keys(resolved).length > 0 ? resolved : undefined;
}

function asObject(value: unknown): Record<string, unknown> {
  return value != null && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim().length > 0 ? value.trim() : undefined;
}

function asFiniteNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function trimTrailingSlash(input: string): string {
  return input.replace(/\/+$/, "");
}

function normalizeEndpointPath(pathValue: string): string {
  const trimmed = pathValue.trim();
  if (!trimmed) return "/v1/audio/speech";
  return trimmed.startsWith("/") ? trimmed : `/${trimmed}`;
}

function normalizeVoice(voice: string | undefined): string | undefined {
  if (!voice) return undefined;
  return voice.trim() || undefined;
}

function normalizeResponseFormat(format: string | undefined): "wav" | "pcm" {
  return format === "pcm" ? "pcm" : "wav";
}

function parseConfig(providerConfig: Record<string, unknown>, cfg?: unknown): PocketTtsConfig {
  const providers = asObject(providerConfig.providers);
  const fromGatewayConfig = extractPocketTtsConfigFromGatewayConfig(cfg);
  const raw = asObject(
    providers.pockettts ??
      providerConfig.pockettts ??
      fromGatewayConfig ??
      providerConfig,
  );

  const baseUrl = trimTrailingSlash(asString(raw.baseUrl) ?? "http://127.0.0.1:8711");
  const endpointPath = normalizeEndpointPath(asString(raw.endpointPath) ?? "/v1/audio/speech");
  const timeoutMs = asFiniteNumber(raw.timeoutMs) ?? 180_000;
  const defaultVoice = normalizeVoice(asString(raw.defaultVoice) ?? asString(raw.defaultVoiceUrl) ?? "alba");
  const responseFormat = normalizeResponseFormat(asString(raw.responseFormat));

  return { baseUrl, endpointPath, timeoutMs, defaultVoice, responseFormat };
}

async function synthesizeViaHttp(opts: {
  url: string;
  text: string;
  timeoutMs: number;
  voice?: string;
  responseFormat: "wav" | "pcm";
}): Promise<Buffer> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), opts.timeoutMs);

  try {
    const response = await fetch(opts.url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "gpt-4o-mini-tts", // ignored by backend; required by OpenAI-compatible payload shape
        input: opts.text,
        voice: opts.voice,
        response_format: opts.responseFormat,
        speed: 1,
        stream_format: "audio",
      }),
      signal: controller.signal,
    });

    if (!response.ok) {
      const detail = await response.text().catch(() => "");
      throw new Error(`PocketTTS server returned ${response.status} ${response.statusText}. ${detail}`);
    }

    const arrayBuffer = await response.arrayBuffer();
    return Buffer.from(arrayBuffer);
  } finally {
    clearTimeout(timeout);
  }
}

export function buildPocketTtsSpeechProvider(): SpeechProviderPlugin {
  return {
    id: "pockettts",
    label: "PocketTTS",
    isConfigured: () => true,
    synthesize: async (req) => {
      const config = parseConfig(req.providerConfig, req.cfg);
      const overrides = asObject(req.providerOverrides);

      const voiceOverride = normalizeVoice(
        asString(overrides.voice) ??
          asString(overrides.voiceUrl) ??
          asString(overrides.voice_url) ??
          asString(overrides.voiceId) ??
          asString(overrides.voice_id),
      );

      const voice = voiceOverride ?? config.defaultVoice;
      const url = `${config.baseUrl}${config.endpointPath}`;

      try {
        const audioBuffer = await synthesizeViaHttp({
          url,
          text: req.text,
          timeoutMs: req.timeoutMs ?? config.timeoutMs,
          voice,
          responseFormat: config.responseFormat,
        });

        return {
          audioBuffer,
          outputFormat: config.responseFormat,
          fileExtension: config.responseFormat === "pcm" ? ".pcm" : ".wav",
          voiceCompatible: false,
        };
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        throw new Error(
          `PocketTTS synthesis failed. Ensure container is running and healthy (GET ${config.baseUrl}/health). ${message}`,
        );
      }
    },
  };
}
