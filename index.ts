import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { buildPocketTtsSpeechProvider } from "./speech-provider.js";

export default definePluginEntry({
  id: "pockettts",
  name: "PocketTTS Speech",
  description: "OpenClaw speech provider using a local PocketTTS server",
  register(api) {
    api.registerSpeechProvider(buildPocketTtsSpeechProvider());
  },
});
