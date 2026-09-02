import { useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import {
  AudioModule,
  RecordingPresets,
  setAudioModeAsync,
  useAudioRecorder,
  useAudioRecorderState,
} from "expo-audio";
import { randomUUID } from "expo-crypto";
import { StatusBar } from "expo-status-bar";
import {
  ArrowLeft,
  Bug,
  Check,
  ChevronRight,
  CircleStop,
  Clock3,
  CloudOff,
  Mic,
  Play,
  RefreshCw,
  Send,
  X,
} from "lucide-react-native";

import { api, syncCapture } from "./src/api";
import { DebugScreen } from "./src/DebugScreen";
import { createCaptureStore, persistBeforeSync, syncPending, type CaptureStore } from "./src/localQueue";
import type {
  LocalCapture,
  DebugSnapshot,
  ResumptionResponse,
  RetrievalCard,
  RetrievalResponse,
  Thought,
} from "./src/types";

type Screen = "capture" | "confirmation" | "capacity" | "results" | "session" | "wrap" | "debug";
type ContextKey = "phone_only" | "out" | "home" | "low_energy";
type Outcome = "done" | "partial" | "stopped" | "spawned_new";
type Fit = "shorter" | "right" | "longer";

const windows = ["5", "15", "30", "60", "a while"] as const;
const contexts: Array<{ key: ContextKey; label: string }> = [
  { key: "phone_only", label: "Phone only" },
  { key: "out", label: "Out" },
  { key: "home", label: "Home" },
  { key: "low_energy", label: "Low energy" },
];

function getDeviceId(): string {
  const key = "loose-thread-device-id";
  const existing = globalThis.localStorage?.getItem(key);
  if (existing) return existing;
  const created = randomUUID();
  globalThis.localStorage?.setItem(key, created);
  return created;
}

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

export default function App() {
  const store = useMemo(() => createCaptureStore(), []);
  const recorder = useAudioRecorder({ ...RecordingPresets.HIGH_QUALITY, directory: "document" });
  const recorderState = useAudioRecorderState(recorder);
  const [screen, setScreen] = useState<Screen>("capture");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [currentCapture, setCurrentCapture] = useState<LocalCapture | null>(null);
  const [thoughts, setThoughts] = useState<Thought[]>([]);
  const [windowLabel, setWindowLabel] = useState<(typeof windows)[number]>("15");
  const [selectedContexts, setSelectedContexts] = useState<Record<ContextKey, boolean>>({
    phone_only: false,
    out: false,
    home: false,
    low_energy: false,
  });
  const [retrieval, setRetrieval] = useState<RetrievalResponse | null>(null);
  const [lastRetrievalId, setLastRetrievalId] = useState<string | null>(
    () => globalThis.localStorage?.getItem("loose-thread-last-retrieval-id") ?? null,
  );
  const [selectedCard, setSelectedCard] = useState<RetrievalCard | null>(null);
  const [resumption, setResumption] = useState<ResumptionResponse | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [spawnSessionId, setSpawnSessionId] = useState<string | null>(null);
  const [fit, setFit] = useState<Fit>("right");
  const [queue, setQueue] = useState<LocalCapture[]>([]);
  const [debugSnapshot, setDebugSnapshot] = useState<DebugSnapshot | null>(null);
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    void (async () => {
      await store.initialize();
      const local = await store.list();
      setQueue(local);
      if (local.some((capture) => capture.status !== "synced")) {
        setNotice("Saved on this device");
        const synced = await syncPending(store, syncCapture);
        setQueue(synced);
      }
    })();
  }, [store]);

  const localPending = queue.filter((capture) => capture.status !== "synced").length;

  async function saveCapture(mode: "text" | "audio", rawText: string | null, audioUri: string | null) {
    const cleanText = rawText?.trim() || null;
    if (mode === "text" && !cleanText) return;
    setBusy(true);
    const id = randomUUID();
    const deviceId = getDeviceId();
    const capture = await persistBeforeSync(store, {
      id,
      deviceId,
      idempotencyKey: `${deviceId}:${id}`,
      mode,
      rawText: cleanText,
      audioUri,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
      clientCreatedAt: new Date().toISOString(),
      parentSessionId: spawnSessionId,
      spawnedThoughtId: spawnSessionId ? randomUUID() : null,
    });
    setCurrentCapture(capture);
    setThoughts([]);
    setNotice("Saved on this device");
    setScreen("confirmation");
    setText("");
    const synced = await syncPending(store, syncCapture);
    setQueue(synced);
    const current = synced.find((item) => item.id === id);
    if (current?.status === "synced") {
      setNotice("Synced");
      if (mode === "text" && !spawnSessionId) await pollCapture(id);
      if (spawnSessionId) setSpawnSessionId(null);
    }
    setBusy(false);
  }

  async function pollCapture(id: string) {
    for (let attempt = 0; attempt < 20; attempt += 1) {
      try {
        const capture = await api.capture(id);
        if (capture.thoughts.length) setThoughts(capture.thoughts);
        if (capture.processing_status === "succeeded" || capture.processing_status === "failed") return;
      } catch {
        return;
      }
      await delay(750);
    }
  }

  async function toggleRecording() {
    if (recorderState.isRecording) {
      await recorder.stop();
      if (recorder.uri) await saveCapture("audio", null, recorder.uri);
      return;
    }
    const permission = await AudioModule.requestRecordingPermissionsAsync();
    if (!permission.granted) {
      Alert.alert("Microphone unavailable", "You can keep this thought as text instead.");
      return;
    }
    await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
    await recorder.prepareToRecordAsync();
    recorder.record();
  }

  async function findOptions() {
    setBusy(true);
    setNotice(null);
    try {
      const response = await api.retrieval({
        id: randomUUID(),
        window: windowLabel,
        contexts: selectedContexts,
      });
      setRetrieval(response);
      setLastRetrievalId(response.id);
      globalThis.localStorage?.setItem("loose-thread-last-retrieval-id", response.id);
      setScreen("results");
    } catch {
      setNotice("Could not reach your saved thoughts just now");
    } finally {
      setBusy(false);
    }
  }

  async function chooseCard(card: RetrievalCard) {
    if (!retrieval) return;
    setBusy(true);
    const id = randomUUID();
    try {
      const [context] = await Promise.all([
        api.resumption(card.thought_id),
        api.startSession({
          id,
          thought_id: card.thought_id,
          retrieval_id: retrieval.id,
          window: retrieval.window,
          idempotency_key: `start:${id}`,
        }),
        api.action(retrieval.id, {
          action: "start",
          thought_id: card.thought_id,
          idempotency_key: `start:${retrieval.id}:${card.thought_id}`,
        }),
      ]);
      setSelectedCard(card);
      setResumption(context);
      setSessionId(id);
      setScreen("session");
    } catch {
      setNotice("This one is still here, but its context is unavailable");
    } finally {
      setBusy(false);
    }
  }

  async function cardAction(card: RetrievalCard, action: "not_now" | "done_with_this") {
    if (!retrieval) return;
    await api.action(retrieval.id, {
      action,
      thought_id: card.thought_id,
      idempotency_key: `${action}:${retrieval.id}:${card.thought_id}`,
    });
    setRetrieval({ ...retrieval, cards: retrieval.cards.filter((item) => item.thought_id !== card.thought_id) });
  }

  async function complete(outcome: Outcome) {
    if (!sessionId) return;
    setBusy(true);
    try {
      await api.completeSession(sessionId, {
        outcome,
        fit,
        idempotency_key: `complete:${sessionId}`,
      });
      if (outcome === "spawned_new") setSpawnSessionId(sessionId);
      resetToCapture();
    } catch {
      setNotice("Your outcome is saved here until sync returns");
    } finally {
      setBusy(false);
    }
  }

  function resetToCapture() {
    setScreen("capture");
    setCurrentCapture(null);
    setThoughts([]);
    setRetrieval(null);
    setSelectedCard(null);
    setResumption(null);
    setSessionId(null);
  }

  async function loadDebug() {
    setScreen("debug");
    setBusy(true);
    const local = await store.list();
    setQueue(local);
    try {
      const [jobs, agentRuns, calibration, feedback, retrievalDebug] = await Promise.all([
        api.jobs(),
        api.agentRuns(),
        api.calibration(),
        api.feedback(),
        lastRetrievalId ? api.retrievalDebug(lastRetrievalId) : Promise.resolve(null),
      ]);
      setDebugSnapshot({ jobs, agentRuns, calibration, feedback, retrieval: retrievalDebug });
    } catch {
      setDebugSnapshot(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={styles.root}>
      <StatusBar style="dark" />
      <Header screen={screen} pending={localPending} onBack={resetToCapture} onDebug={loadDebug} />
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        {screen === "capture" && (
          <CaptureScreen
            text={text}
            recording={recorderState.isRecording}
            duration={recorderState.durationMillis}
            spawnMode={Boolean(spawnSessionId)}
            onChangeText={setText}
            onSubmit={() => void saveCapture("text", text, null)}
            onRecord={() => void toggleRecording()}
            onBrowse={() => setScreen("capacity")}
          />
        )}
        {screen === "confirmation" && currentCapture && (
          <ConfirmationScreen
            capture={currentCapture}
            thoughts={thoughts}
            notice={notice}
            onContinue={() => setScreen("capacity")}
            onRetry={() => void saveCapture(currentCapture.mode, currentCapture.rawText, currentCapture.audioUri)}
          />
        )}
        {screen === "capacity" && (
          <CapacityScreen
            windowLabel={windowLabel}
            selectedContexts={selectedContexts}
            onWindow={setWindowLabel}
            onContext={(key) =>
              setSelectedContexts((current) => ({ ...current, [key]: !current[key] }))
            }
            onSubmit={() => void findOptions()}
          />
        )}
        {screen === "results" && retrieval && (
          <ResultsScreen retrieval={retrieval} onChoose={chooseCard} onAction={cardAction} />
        )}
        {screen === "session" && selectedCard && resumption && (
          <SessionScreen card={selectedCard} resumption={resumption} onWrap={() => setScreen("wrap")} />
        )}
        {screen === "wrap" && (
          <WrapScreen fit={fit} onFit={setFit} onComplete={(outcome) => void complete(outcome)} />
        )}
        {screen === "debug" && (
          <DebugScreen
            queue={queue}
            snapshot={debugSnapshot}
            loading={busy}
            onRefresh={() => void loadDebug()}
          />
        )}
        {notice && screen !== "confirmation" && <Text style={styles.notice}>{notice}</Text>}
        {busy && <ActivityIndicator style={styles.loader} color="#2D6A4F" />}
      </ScrollView>
    </View>
  );
}

function Header({
  screen,
  pending,
  onBack,
  onDebug,
}: {
  screen: Screen;
  pending: number;
  onBack: () => void;
  onDebug: () => void;
}) {
  return (
    <View style={styles.header}>
      {screen !== "capture" ? (
        <IconButton label="Back to capture" onPress={onBack} icon={<ArrowLeft size={21} color="#17211B" />} />
      ) : (
        <View style={styles.logoMark}><View style={styles.logoLine} /><View style={styles.logoDot} /></View>
      )}
      <Text style={styles.brand}>Loose Thread</Text>
      <View style={styles.headerActions}>
        {pending > 0 && <CloudOff size={17} color="#C05A3D" />}
        <IconButton label="Diagnostics" onPress={onDebug} icon={<Bug size={20} color="#17211B" />} />
      </View>
    </View>
  );
}

function CaptureScreen(props: {
  text: string;
  recording: boolean;
  duration: number;
  spawnMode: boolean;
  onChangeText: (value: string) => void;
  onSubmit: () => void;
  onRecord: () => void;
  onBrowse: () => void;
}) {
  return (
    <View style={styles.section}>
      <Text style={styles.eyebrow}>{props.spawnMode ? "A new thread from this session" : "CAPTURE"}</Text>
      <Text style={styles.title}>What’s something you don’t want to lose?</Text>
      <View style={styles.composer}>
        <TextInput
          value={props.text}
          onChangeText={props.onChangeText}
          placeholder="Put it here as it comes to you"
          placeholderTextColor="#758078"
          multiline
          style={styles.input}
        />
        <Pressable
          accessibilityLabel="Save text thought"
          disabled={!props.text.trim()}
          onPress={props.onSubmit}
          style={({ pressed }) => [styles.sendButton, pressed && styles.pressed, !props.text.trim() && styles.disabled]}
        >
          <Send size={21} color="#FFFFFF" />
        </Pressable>
      </View>
      <View style={styles.orRow}><View style={styles.rule} /><Text style={styles.orText}>OR SAY IT</Text><View style={styles.rule} /></View>
      <Pressable
        accessibilityLabel={props.recording ? "Stop recording" : "Record a voice thought"}
        onPress={props.onRecord}
        style={({ pressed }) => [styles.micButton, props.recording && styles.micActive, pressed && styles.pressed]}
      >
        {props.recording ? <CircleStop size={34} color="#FFFFFF" /> : <Mic size={36} color="#FFFFFF" />}
      </Pressable>
      <Text style={styles.recordLabel}>
        {props.recording ? `${Math.floor(props.duration / 1000)}s · tap to keep` : "Tap to record"}
      </Text>
      {!props.spawnMode && (
        <Pressable
          accessibilityLabel="See what fits without capturing"
          onPress={props.onBrowse}
          style={({ pressed }) => [styles.browseButton, pressed && styles.pressed]}
        >
          <Clock3 size={18} color="#355C7D" />
          <Text style={styles.browseButtonText}>See what fits</Text>
          <ChevronRight size={18} color="#355C7D" />
        </Pressable>
      )}
    </View>
  );
}

function ConfirmationScreen(props: {
  capture: LocalCapture;
  thoughts: Thought[];
  notice: string | null;
  onContinue: () => void;
  onRetry: () => void;
}) {
  return (
    <View style={styles.section}>
      <View style={styles.savedIcon}><Check size={28} color="#FFFFFF" /></View>
      <Text style={styles.title}>Kept.</Text>
      <Text style={styles.subtitle}>{props.notice ?? "Working out where it belongs"}</Text>
      <View style={styles.thoughtList}>
        {props.thoughts.length ? (
          props.thoughts.map((thought) => (
            <View key={thought.id} style={styles.thoughtItem}>
              <View style={styles.metaRow}>
                <Text style={styles.meta}>{thought.kind}</Text>
                <Text style={styles.thoughtMeta}>
                  {thought.duration_bucket} | {thought.energy} | {thought.commitment_strength}
                </Text>
              </View>
              <Text style={styles.thoughtText}>{thought.refined_text}</Text>
              <Text style={styles.thoughtDetail}>
                {thought.contexts.length ? thought.contexts.join(", ") : "any context"} | {thought.open_loop.is_open ? "open loop" : "closed loop"} | {thought.surface_policy}
              </Text>
            </View>
          ))
        ) : (
          <Text style={styles.thoughtText}>
            {props.capture.rawText ?? "Voice thought saved on this device"}
          </Text>
        )}
      </View>
      <PrimaryButton label="Find something for now" onPress={props.onContinue} icon={<Clock3 size={19} color="#FFFFFF" />} />
      {props.capture.status === "failed" && <TextButton label="Try sync again" onPress={props.onRetry} icon={<RefreshCw size={17} color="#2D6A4F" />} />}
    </View>
  );
}

function CapacityScreen(props: {
  windowLabel: (typeof windows)[number];
  selectedContexts: Record<ContextKey, boolean>;
  onWindow: (value: (typeof windows)[number]) => void;
  onContext: (key: ContextKey) => void;
  onSubmit: () => void;
}) {
  return (
    <View style={styles.section}>
      <Text style={styles.eyebrow}>RIGHT NOW</Text>
      <Text style={styles.title}>How much room do you have?</Text>
      <View style={styles.segmented}>
        {windows.map((item) => (
          <Pressable key={item} onPress={() => props.onWindow(item)} style={[styles.segment, props.windowLabel === item && styles.segmentActive]}>
            <Text style={[styles.segmentText, props.windowLabel === item && styles.segmentTextActive]}>{item}</Text>
          </Pressable>
        ))}
      </View>
      <Text style={styles.label}>A little more context</Text>
      <View style={styles.chips}>
        {contexts.map((item) => (
          <Pressable key={item.key} onPress={() => props.onContext(item.key)} style={[styles.chip, props.selectedContexts[item.key] && styles.chipActive]}>
            <Text style={[styles.chipText, props.selectedContexts[item.key] && styles.chipTextActive]}>{item.label}</Text>
          </Pressable>
        ))}
      </View>
      <PrimaryButton label="Show me what fits" onPress={props.onSubmit} icon={<ChevronRight size={20} color="#FFFFFF" />} />
    </View>
  );
}

function ResultsScreen({
  retrieval,
  onChoose,
  onAction,
}: {
  retrieval: RetrievalResponse;
  onChoose: (card: RetrievalCard) => void;
  onAction: (card: RetrievalCard, action: "not_now" | "done_with_this") => void;
}) {
  return (
    <View style={styles.section}>
      <Text style={styles.eyebrow}>A FEW THAT FIT</Text>
      <Text style={styles.title}>See what catches.</Text>
      {retrieval.cards.length === 0 && <Text style={styles.empty}>Nothing good fits those edges right now.</Text>}
      {retrieval.cards.slice(0, 3).map((card) => (
        <View key={card.thought_id} style={styles.optionCard}>
          <View style={styles.metaRow}><Text style={styles.meta}>{card.kind}</Text><Text style={styles.bucket}>{card.duration_bucket}</Text></View>
          <Text style={styles.cardTitle}>{card.refined_text}</Text>
          <Pressable onPress={() => onChoose(card)} style={styles.startRow}><Play size={17} color="#FFFFFF" fill="#FFFFFF" /><Text style={styles.startText}>{card.open_loop.is_open ? "Pick this back up" : "Start"}</Text></Pressable>
          <View style={styles.cardActions}>
            <TextButton label="Not now" onPress={() => void onAction(card, "not_now")} icon={<Clock3 size={16} color="#355C7D" />} />
            <TextButton label="Done with this" onPress={() => void onAction(card, "done_with_this")} icon={<X size={16} color="#355C7D" />} />
          </View>
        </View>
      ))}
    </View>
  );
}

function SessionScreen({ card, resumption, onWrap }: { card: RetrievalCard; resumption: ResumptionResponse; onWrap: () => void }) {
  return (
    <View style={styles.section}>
      <Text style={styles.eyebrow}>IN SESSION</Text>
      <Text style={styles.title}>{card.refined_text}</Text>
      <View style={styles.contextBand}>
        <Text style={styles.contextLabel}>ORIGINAL NOTE</Text>
        <Text style={styles.contextText}>{resumption.raw_fragment}</Text>
      </View>
      {resumption.where_you_got_to && <View style={styles.resumeBlock}><Text style={styles.label}>Where you got to</Text><Text style={styles.resumeText}>{resumption.where_you_got_to}</Text></View>}
      {resumption.supporting_thoughts.length > 0 && (
        <View style={styles.resumeBlock}>
          <Text style={styles.label}>Supporting thread</Text>
          {resumption.supporting_thoughts.map((thought) => (
            <View key={thought.id} style={styles.evidenceRow}>
              <Text style={styles.evidenceRelation}>{thought.relation_type}</Text>
              <Text style={styles.evidenceText}>{thought.refined_text}</Text>
            </View>
          ))}
        </View>
      )}
      {resumption.unresolved_loop && <Text style={styles.unresolved}>{resumption.unresolved_loop}</Text>}
      {resumption.suggested_prompt && (
        <View style={styles.contextBand}>
          <Text style={styles.contextLabel}>NEXT PROMPT</Text>
          <Text style={styles.contextText}>{resumption.suggested_prompt}</Text>
        </View>
      )}
      <PrimaryButton label="Wrap this session" onPress={onWrap} icon={<Check size={19} color="#FFFFFF" />} />
    </View>
  );
}

function WrapScreen({ fit, onFit, onComplete }: { fit: Fit; onFit: (fit: Fit) => void; onComplete: (outcome: Outcome) => void }) {
  return (
    <View style={styles.section}>
      <Text style={styles.eyebrow}>WRAP</Text><Text style={styles.title}>How did that land?</Text>
      <Text style={styles.label}>Did it fit?</Text>
      <View style={styles.chips}>{(["shorter", "right", "longer"] as Fit[]).map((item) => <Pressable key={item} onPress={() => onFit(item)} style={[styles.chip, fit === item && styles.chipActive]}><Text style={[styles.chipText, fit === item && styles.chipTextActive]}>{item === "right" ? "About right" : item === "shorter" ? "Shorter" : "Longer"}</Text></Pressable>)}</View>
      <Text style={styles.label}>Where did you land?</Text>
      <View style={styles.outcomeList}>
        {([ ["done", "Done"], ["partial", "Partway"], ["stopped", "Stopped here"], ["spawned_new", "Something new came up"] ] as Array<[Outcome, string]>).map(([value, label]) => (
          <Pressable key={value} onPress={() => onComplete(value)} style={styles.outcomeRow}><Text style={styles.outcomeText}>{label}</Text><ChevronRight size={19} color="#2D6A4F" /></Pressable>
        ))}
      </View>
    </View>
  );
}

function PrimaryButton({ label, onPress, icon }: { label: string; onPress: () => void; icon: React.ReactNode }) {
  return <Pressable onPress={onPress} style={({ pressed }) => [styles.primary, pressed && styles.pressed]}>{icon}<Text style={styles.primaryText}>{label}</Text></Pressable>;
}
function TextButton({ label, onPress, icon }: { label: string; onPress: () => void; icon: React.ReactNode }) {
  return <Pressable onPress={onPress} style={({ pressed }) => [styles.textButton, pressed && styles.pressed]}>{icon}<Text style={styles.textButtonText}>{label}</Text></Pressable>;
}
function IconButton({ label, onPress, icon }: { label: string; onPress: () => void; icon: React.ReactNode }) {
  return <Pressable accessibilityLabel={label} onPress={onPress} style={({ pressed }) => [styles.iconButton, pressed && styles.pressed]}>{icon}</Pressable>;
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#F3F4EF", paddingTop: Platform.OS === "android" ? 24 : 0 },
  header: { height: 66, paddingHorizontal: 20, borderBottomWidth: 1, borderBottomColor: "#D8DDD7", flexDirection: "row", alignItems: "center" },
  brand: { flex: 1, fontSize: 20, lineHeight: 25, fontWeight: "700", color: "#17211B" },
  headerActions: { flexDirection: "row", alignItems: "center", gap: 8 },
  iconButton: { width: 42, height: 42, alignItems: "center", justifyContent: "center" },
  logoMark: { width: 42, height: 42, justifyContent: "center" }, logoLine: { width: 23, height: 3, backgroundColor: "#2D6A4F", transform: [{ rotate: "-12deg" }] }, logoDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: "#C05A3D", marginLeft: 22, marginTop: -6 },
  scroll: { flexGrow: 1, paddingHorizontal: 20, paddingBottom: 48 },
  section: { width: "100%", maxWidth: 680, alignSelf: "center", paddingTop: 42, gap: 20 },
  eyebrow: { fontSize: 12, lineHeight: 16, fontWeight: "800", color: "#2D6A4F" },
  title: { fontSize: 34, lineHeight: 41, fontWeight: "700", color: "#17211B" },
  subtitle: { fontSize: 16, lineHeight: 24, color: "#59655D" },
  composer: { minHeight: 142, borderWidth: 1, borderColor: "#BFC7C0", borderRadius: 8, backgroundColor: "#FFFFFF", padding: 16, flexDirection: "row", alignItems: "flex-end" },
  input: { flex: 1, minHeight: 104, fontSize: 18, lineHeight: 27, color: "#17211B", textAlignVertical: "top" },
  sendButton: { width: 46, height: 46, borderRadius: 6, backgroundColor: "#2D6A4F", alignItems: "center", justifyContent: "center" },
  orRow: { flexDirection: "row", alignItems: "center", gap: 12 }, rule: { flex: 1, height: 1, backgroundColor: "#D8DDD7" }, orText: { fontSize: 11, fontWeight: "700", color: "#758078" },
  micButton: { width: 92, height: 92, borderRadius: 46, alignSelf: "center", alignItems: "center", justifyContent: "center", backgroundColor: "#C05A3D", borderWidth: 7, borderColor: "#E8CFC7" },
  micActive: { backgroundColor: "#8F3328" }, recordLabel: { textAlign: "center", fontSize: 15, color: "#59655D" },
  browseButton: { minHeight: 52, borderTopWidth: 1, borderBottomWidth: 1, borderColor: "#D8DDD7", paddingHorizontal: 8, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 9 },
  browseButtonText: { color: "#355C7D", fontSize: 16, fontWeight: "700" },
  pressed: { opacity: 0.72 }, disabled: { opacity: 0.35 },
  savedIcon: { width: 56, height: 56, borderRadius: 28, backgroundColor: "#2D6A4F", alignItems: "center", justifyContent: "center" },
  thoughtList: { borderTopWidth: 1, borderBottomWidth: 1, borderColor: "#D8DDD7", paddingVertical: 8 }, thoughtItem: { borderBottomWidth: 1, borderBottomColor: "#E4E7E2", paddingVertical: 12, gap: 4 }, thoughtText: { fontSize: 19, lineHeight: 28, color: "#17211B", paddingVertical: 8 }, thoughtMeta: { flex: 1, textAlign: "right", fontSize: 11, lineHeight: 17, color: "#59655D" }, thoughtDetail: { fontSize: 12, lineHeight: 18, color: "#355C7D" },
  primary: { minHeight: 52, borderRadius: 6, backgroundColor: "#2D6A4F", paddingHorizontal: 18, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 10 }, primaryText: { color: "#FFFFFF", fontSize: 16, fontWeight: "700" },
  textButton: { minHeight: 40, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 7, paddingHorizontal: 8 }, textButtonText: { color: "#355C7D", fontSize: 14, fontWeight: "600" },
  segmented: { flexDirection: "row", borderWidth: 1, borderColor: "#BFC7C0", borderRadius: 6, overflow: "hidden" }, segment: { flex: 1, minHeight: 48, alignItems: "center", justifyContent: "center", backgroundColor: "#FFFFFF", borderRightWidth: 1, borderRightColor: "#D8DDD7" }, segmentActive: { backgroundColor: "#17211B" }, segmentText: { fontSize: 14, color: "#354139" }, segmentTextActive: { color: "#FFFFFF", fontWeight: "700" },
  label: { marginTop: 10, fontSize: 14, lineHeight: 20, fontWeight: "700", color: "#354139" }, chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 }, chip: { minHeight: 40, borderRadius: 20, borderWidth: 1, borderColor: "#BFC7C0", backgroundColor: "#FFFFFF", paddingHorizontal: 15, alignItems: "center", justifyContent: "center" }, chipActive: { borderColor: "#355C7D", backgroundColor: "#E5EBF0" }, chipText: { fontSize: 14, color: "#59655D" }, chipTextActive: { color: "#27455F", fontWeight: "700" },
  optionCard: { borderWidth: 1, borderColor: "#C9D0CA", borderRadius: 8, backgroundColor: "#FFFFFF", padding: 18, gap: 15 }, metaRow: { flexDirection: "row", justifyContent: "space-between" }, meta: { fontSize: 12, fontWeight: "700", textTransform: "uppercase", color: "#2D6A4F" }, bucket: { fontSize: 12, fontWeight: "700", color: "#C05A3D" }, cardTitle: { fontSize: 21, lineHeight: 29, fontWeight: "600", color: "#17211B" }, startRow: { minHeight: 46, borderRadius: 6, backgroundColor: "#2D6A4F", flexDirection: "row", gap: 9, alignItems: "center", justifyContent: "center" }, startText: { color: "#FFFFFF", fontWeight: "700" }, cardActions: { flexDirection: "row", justifyContent: "space-between", flexWrap: "wrap" },
  contextBand: { backgroundColor: "#E5EBF0", borderLeftWidth: 4, borderLeftColor: "#355C7D", padding: 16 }, contextLabel: { fontSize: 11, fontWeight: "800", color: "#355C7D", marginBottom: 8 }, contextText: { fontSize: 16, lineHeight: 24, color: "#2D3942" }, resumeBlock: { borderTopWidth: 1, borderColor: "#D8DDD7", paddingTop: 10, gap: 8 }, resumeText: { fontSize: 18, lineHeight: 27, color: "#17211B" }, evidenceRow: { borderLeftWidth: 3, borderLeftColor: "#BFC7C0", paddingLeft: 10, gap: 2 }, evidenceRelation: { fontSize: 11, lineHeight: 16, fontWeight: "700", textTransform: "uppercase", color: "#355C7D" }, evidenceText: { fontSize: 14, lineHeight: 21, color: "#354139" }, unresolved: { fontSize: 16, lineHeight: 24, color: "#7D4034" },
  outcomeList: { borderTopWidth: 1, borderColor: "#D8DDD7" }, outcomeRow: { minHeight: 58, borderBottomWidth: 1, borderColor: "#D8DDD7", flexDirection: "row", alignItems: "center", justifyContent: "space-between" }, outcomeText: { fontSize: 17, color: "#17211B", fontWeight: "600" },
  empty: { paddingVertical: 26, fontSize: 17, lineHeight: 25, color: "#59655D" }, notice: { textAlign: "center", color: "#7D4034", marginTop: 20, fontSize: 14 }, loader: { marginTop: 24 },
});
