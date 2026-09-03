import type { ReactNode } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import {
  Activity,
  BrainCircuit,
  Check,
  Cloud,
  CloudOff,
  ChevronRight,
  Database,
  GitBranch,
  RefreshCw,
  SlidersHorizontal,
  Workflow,
} from "lucide-react-native";

import type { DebugSnapshot, LocalCapture } from "./types";
import { buildProcessSteps, type ProcessStep } from "./processTrace";

type DebugScreenProps = {
  queue: LocalCapture[];
  snapshot: DebugSnapshot | null;
  loading: boolean;
  onRefresh: () => void;
  onOpenThought: (thoughtId: string) => void;
};

const componentLabels: Record<string, string> = {
  rediscovery_value: "Rediscovery",
  capacity_fit: "Capacity fit",
  context_fit: "Context fit",
  open_loop_value: "Open loop",
  thread_momentum: "Thread momentum",
  personal_kind_affinity: "Learned kind affinity",
  explicit_temporal_relevance: "Time relevance",
  novelty: "Novelty",
  fatigue_penalty: "Fatigue penalty",
  rejection_penalty: "Rejection penalty",
};

export function DebugScreen({ queue, snapshot, loading, onRefresh, onOpenThought }: DebugScreenProps) {
  const processSteps = buildProcessSteps(snapshot);
  const knownThoughtIds = getKnownThoughtIds(snapshot);

  return (
    <View style={styles.section}>
      <View style={styles.titleRow}>
        <View style={styles.titleCopy}>
          <Text style={styles.eyebrow}>SYSTEM STATE</Text>
          <Text style={styles.title}>Architecture inspector</Text>
        </View>
        <Pressable
          accessibilityLabel="Refresh diagnostics"
          onPress={onRefresh}
          style={({ pressed }) => [styles.iconButton, pressed && styles.pressed]}
        >
          <RefreshCw size={20} color="#17211B" />
        </Pressable>
      </View>

      <DebugSection icon={<GitBranch size={18} color="#355C7D" />} title="Latest end-to-end process">
        {processSteps.map((step, index) => (
          <ProcessTraceRow
            key={`${step.actor}-${step.title}-${index}`}
            step={step}
            index={index}
            last={index === processSteps.length - 1}
            onOpenThought={onOpenThought}
          />
        ))}
        {!processSteps.length ? <Text style={styles.empty}>No persisted process evidence yet.</Text> : null}
      </DebugSection>

      <DebugSection icon={<Database size={18} color="#355C7D" />} title="Local persistence">
        {queue.slice(0, 6).map((item) => (
          <View key={item.id} style={styles.row}>
            {item.status === "synced" ? (
              <Cloud size={17} color="#2D6A4F" />
            ) : (
              <CloudOff size={17} color="#C05A3D" />
            )}
            <View style={styles.rowCopy}>
              <Text style={styles.rowTitle}>{item.mode} capture</Text>
              <Text style={styles.rowMeta}>
                {item.status} | attempt {item.attempts} | {shortId(item.id)}
              </Text>
            </View>
          </View>
        ))}
        {queue.length === 0 ? <Text style={styles.empty}>No local captures.</Text> : null}
      </DebugSection>

      <DebugSection icon={<Workflow size={18} color="#355C7D" />} title="Durable orchestration">
        {snapshot?.jobs.slice(0, 10).map((job) => (
          <View key={job.id} style={styles.row}>
            <StatusDot status={job.status} />
            <View style={styles.rowCopy}>
              <Text style={styles.rowTitle}>{humanize(job.job_type)}</Text>
              <Text style={styles.rowMeta}>
                {job.status} | attempt {job.attempts}/{job.max_attempts} | correlation {shortId(job.correlation_id)}
              </Text>
            </View>
          </View>
        ))}
      </DebugSection>

      <DebugSection icon={<BrainCircuit size={18} color="#355C7D" />} title="Agent runs">
        {snapshot?.agentRuns.slice(0, 8).map((run) => (
          <View key={run.id} style={styles.runRow}>
            <View style={styles.rowHeading}>
              <Text style={styles.rowTitle}>{humanize(run.agent_name)}</Text>
              <Text style={[styles.runStatus, run.status === "succeeded" && styles.successText]}>
                {run.status}
              </Text>
            </View>
            <Text style={styles.rowMeta}>
              {run.model} | {run.latency_ms ?? 0} ms | prompt {run.prompt_version}
            </Text>
            <Text style={styles.traceText}>
              trace {run.openai_trace_id ? shortId(run.openai_trace_id, 18) : "unavailable"} | run {shortId(run.id)}
            </Text>
            <EntityIds
              label="inputs"
              ids={run.input_entity_ids}
              knownThoughtIds={knownThoughtIds}
              onOpenThought={onOpenThought}
            />
            <EntityIds
              label="outputs"
              ids={run.output_entity_ids}
              knownThoughtIds={knownThoughtIds}
              onOpenThought={onOpenThought}
            />
          </View>
        ))}
        {!snapshot?.agentRuns.length ? <Text style={styles.empty}>No agent runs yet.</Text> : null}
      </DebugSection>

      <DebugSection icon={<Activity size={18} color="#355C7D" />} title="Latest deterministic ranking">
        {snapshot?.retrieval ? (
          <>
            <Text style={styles.sectionMeta}>
              {snapshot.retrieval.retrieval.ranking_version} | {snapshot.retrieval.retrieval.candidate_count} candidates
            </Text>
            {snapshot.retrieval.impressions.slice(0, 5).map((impression) => (
              <Pressable
                accessibilityLabel={`Open ranked thread ${shortId(impression.thought_id)}`}
                key={impression.thought_id}
                onPress={() => onOpenThought(impression.thought_id)}
                style={({ pressed }) => [styles.rankingBlock, pressed && styles.pressed]}
              >
                <View style={styles.rowHeading}>
                  <Text style={styles.rowTitle}>
                    Rank {impression.rank_position} | score {Number(impression.score).toFixed(3)}
                  </Text>
                  {impression.selected ? <Check size={17} color="#2D6A4F" /> : null}
                  <ChevronRight size={17} color="#355C7D" />
                </View>
                <Text style={styles.traceText}>thought {shortId(impression.thought_id)}</Text>
                {Object.entries(impression.score_components).map(([name, value]) => (
                  <ScoreComponent key={name} name={name} value={Number(value)} />
                ))}
              </Pressable>
            ))}
          </>
        ) : (
          <Text style={styles.empty}>Request a fit to inspect ranking scores.</Text>
        )}
      </DebugSection>

      <DebugSection icon={<Activity size={18} color="#355C7D" />} title="Feedback events">
        {snapshot?.feedback.slice(0, 8).map((event) => (
          <View key={event.id} style={styles.row}>
            <StatusDot status={event.calibration_applied_at ? "succeeded" : "queued"} />
            <View style={styles.rowCopy}>
              <Text style={styles.rowTitle}>{humanize(event.event_type)}</Text>
              <Text style={styles.rowMeta}>
                {feedbackSummary(event.event_data)} | {event.calibration_applied_at ? event.calibration_version : "awaiting calibration"}
              </Text>
            </View>
          </View>
        ))}
        {!snapshot?.feedback.length ? <Text style={styles.empty}>No feedback events yet.</Text> : null}
      </DebugSection>

      <DebugSection icon={<SlidersHorizontal size={18} color="#355C7D" />} title="Learned calibration">
        {snapshot ? (
          <>
            <Text style={styles.observationCount}>
              {snapshot.calibration.observation_count} applied observations
            </Text>
            <CalibrationMap label="Kind affinity" values={snapshot.calibration.kind_affinity} />
            <CalibrationMap label="Duration adjustment" values={snapshot.calibration.duration_calibration} signed />
            <CalibrationMap label="Context affinity" values={snapshot.calibration.context_affinity} />
          </>
        ) : (
          <Text style={styles.empty}>Cloud diagnostics unavailable.</Text>
        )}
      </DebugSection>

      {loading ? <Text style={styles.loading}>Refreshing...</Text> : null}
    </View>
  );
}

function ProcessTraceRow({
  step,
  index,
  last,
  onOpenThought,
}: {
  step: ProcessStep;
  index: number;
  last: boolean;
  onOpenThought: (thoughtId: string) => void;
}) {
  return (
    <View style={styles.processRow}>
      <View style={styles.processRail}>
        <View style={[styles.processIndex, isComplete(step.status) && styles.processIndexComplete]}>
          <Text style={[styles.processIndexText, isComplete(step.status) && styles.processIndexTextComplete]}>
            {index + 1}
          </Text>
        </View>
        {!last ? <View style={styles.processLine} /> : null}
      </View>
      <View style={styles.processCopy}>
        <View style={styles.rowHeading}>
          <Text style={styles.processActor}>{step.actor}</Text>
          <Text style={[styles.runStatus, isComplete(step.status) && styles.successText]}>{step.status}</Text>
        </View>
        <Text style={styles.processTitle}>{step.title}</Text>
        <Text style={styles.rowMeta}>{step.detail}</Text>
        {step.thoughtIds?.length ? (
          <View style={styles.threadLinks}>
            {step.thoughtIds.slice(0, 3).map((thoughtId) => (
              <Pressable
                accessibilityLabel={`Open thread ${shortId(thoughtId)}`}
                key={thoughtId}
                onPress={() => onOpenThought(thoughtId)}
                style={({ pressed }) => [styles.threadLink, pressed && styles.pressed]}
              >
                <Text style={styles.threadLinkText}>{shortId(thoughtId)}</Text>
                <ChevronRight size={14} color="#355C7D" />
              </Pressable>
            ))}
          </View>
        ) : null}
      </View>
    </View>
  );
}

function EntityIds({
  label,
  ids,
  knownThoughtIds,
  onOpenThought,
}: {
  label: string;
  ids: string[];
  knownThoughtIds: Set<string>;
  onOpenThought: (thoughtId: string) => void;
}) {
  if (!ids.length) return <Text style={styles.entityText}>{label} none</Text>;
  return (
    <View style={styles.entityRow}>
      <Text style={styles.entityText}>{label}</Text>
      {ids.slice(0, 3).map((id) =>
        knownThoughtIds.has(id) ? (
          <Pressable
            accessibilityLabel={`Open thread ${shortId(id)}`}
            key={id}
            onPress={() => onOpenThought(id)}
            style={({ pressed }) => [styles.inlineEntityLink, pressed && styles.pressed]}
          >
            <Text style={styles.threadLinkText}>{shortId(id)}</Text>
            <ChevronRight size={12} color="#355C7D" />
          </Pressable>
        ) : (
          <Text key={id} style={styles.entityText}>{shortId(id)}</Text>
        ),
      )}
      {ids.length > 3 ? <Text style={styles.entityText}>+{ids.length - 3}</Text> : null}
    </View>
  );
}

function DebugSection({
  icon,
  title,
  children,
}: {
  icon: ReactNode;
  title: string;
  children: ReactNode;
}) {
  return (
    <View style={styles.debugSection}>
      <View style={styles.sectionHeading}>
        {icon}
        <Text style={styles.sectionTitle}>{title}</Text>
      </View>
      {children}
    </View>
  );
}

function StatusDot({ status }: { status: string }) {
  const color = isComplete(status) ? "#2D6A4F" : status === "dead_letter" ? "#8F3328" : "#C05A3D";
  return <View style={[styles.statusDot, { backgroundColor: color }]} />;
}

function isComplete(status: string): boolean {
  return ["succeeded", "calibrated", "persisted"].includes(status);
}

function ScoreComponent({ name, value }: { name: string; value: number }) {
  const normalized = Math.max(0, Math.min(1, value));
  return (
    <View style={styles.scoreRow}>
      <Text style={styles.scoreLabel}>{componentLabels[name] ?? humanize(name)}</Text>
      <View style={styles.scoreTrack}>
        <View style={[styles.scoreFill, { width: `${normalized * 100}%` as `${number}%` }]} />
      </View>
      <Text style={styles.scoreValue}>{value.toFixed(2)}</Text>
    </View>
  );
}

function CalibrationMap({
  label,
  values,
  signed = false,
}: {
  label: string;
  values: Record<string, number>;
  signed?: boolean;
}) {
  const entries = Object.entries(values);
  return (
    <View style={styles.calibrationGroup}>
      <Text style={styles.calibrationLabel}>{label}</Text>
      {entries.length ? (
        entries.map(([name, value]) => (
          <View key={name} style={styles.valueRow}>
            <Text style={styles.valueName}>{humanize(name)}</Text>
            <Text style={styles.valueNumber}>
              {signed && value >= 0 ? "+" : ""}{value.toFixed(2)}
            </Text>
          </View>
        ))
      ) : (
        <Text style={styles.rowMeta}>No learned values.</Text>
      )}
    </View>
  );
}

function feedbackSummary(data: Record<string, unknown>): string {
  const values = [data.action, data.outcome, data.fit, data.window].filter(
    (value): value is string => typeof value === "string",
  );
  return values.length ? values.join(" | ") : "recorded";
}

function humanize(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function shortId(value: string, length = 10): string {
  return value.length <= length ? value : value.slice(0, length);
}

function getKnownThoughtIds(snapshot: DebugSnapshot | null): Set<string> {
  const ids = new Set<string>();
  snapshot?.retrieval?.impressions.forEach((item) => ids.add(item.thought_id));
  snapshot?.feedback.forEach((event) => {
    if (event.thought_id) ids.add(event.thought_id);
  });
  snapshot?.agentRuns.forEach((run) => {
    if (run.agent_name === "thought_interpreter") run.output_entity_ids.forEach((id) => ids.add(id));
    if (run.agent_name === "continuity_agent") run.input_entity_ids.forEach((id) => ids.add(id));
    if (run.agent_name === "resumption_agent") {
      run.input_entity_ids.forEach((id) => ids.add(id));
      run.output_entity_ids.forEach((id) => ids.add(id));
    }
  });
  return ids;
}

const styles = StyleSheet.create({
  section: { width: "100%", maxWidth: 760, alignSelf: "center", paddingTop: 32, gap: 24 },
  titleRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 16 },
  titleCopy: { flex: 1, gap: 6 },
  eyebrow: { fontSize: 12, lineHeight: 16, fontWeight: "800", color: "#2D6A4F" },
  title: { fontSize: 30, lineHeight: 37, fontWeight: "700", color: "#17211B" },
  iconButton: { width: 42, height: 42, alignItems: "center", justifyContent: "center" },
  pressed: { opacity: 0.68 },
  debugSection: { borderTopWidth: 1, borderTopColor: "#BFC7C0", paddingTop: 14, gap: 4 },
  sectionHeading: { minHeight: 34, flexDirection: "row", alignItems: "center", gap: 9 },
  sectionTitle: { fontSize: 16, lineHeight: 22, fontWeight: "700", color: "#17211B" },
  sectionMeta: { fontSize: 12, lineHeight: 18, color: "#59655D", marginBottom: 8 },
  row: { minHeight: 50, borderBottomWidth: 1, borderBottomColor: "#D8DDD7", flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 8 },
  rowCopy: { flex: 1, minWidth: 0 },
  rowHeading: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12 },
  rowTitle: { flex: 1, fontSize: 14, lineHeight: 20, fontWeight: "700", color: "#243028" },
  rowMeta: { fontSize: 12, lineHeight: 18, color: "#59655D" },
  traceText: { fontSize: 11, lineHeight: 17, color: "#355C7D" },
  entityText: { fontSize: 11, lineHeight: 17, color: "#59655D" },
  entityRow: { minHeight: 26, flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 6 },
  inlineEntityLink: { minHeight: 24, flexDirection: "row", alignItems: "center", gap: 2, borderBottomWidth: 1, borderBottomColor: "#9AACB8" },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  runRow: { borderBottomWidth: 1, borderBottomColor: "#D8DDD7", paddingVertical: 10, gap: 2 },
  runStatus: { fontSize: 11, lineHeight: 17, fontWeight: "700", color: "#7D4034" },
  successText: { color: "#2D6A4F" },
  processRow: { minHeight: 78, flexDirection: "row", gap: 12 },
  processRail: { width: 28, alignItems: "center" },
  processIndex: { width: 24, height: 24, borderRadius: 12, borderWidth: 1, borderColor: "#C05A3D", alignItems: "center", justifyContent: "center" },
  processIndexComplete: { backgroundColor: "#2D6A4F", borderColor: "#2D6A4F" },
  processIndexText: { fontSize: 11, lineHeight: 15, fontWeight: "800", color: "#7D4034" },
  processIndexTextComplete: { color: "#FFFFFF" },
  processLine: { flex: 1, width: 1, backgroundColor: "#BFC7C0", marginVertical: 3 },
  processCopy: { flex: 1, minWidth: 0, borderBottomWidth: 1, borderBottomColor: "#D8DDD7", paddingBottom: 12, gap: 2 },
  processActor: { flex: 1, fontSize: 11, lineHeight: 16, fontWeight: "800", color: "#355C7D", textTransform: "uppercase" },
  processTitle: { fontSize: 14, lineHeight: 20, fontWeight: "700", color: "#243028" },
  threadLinks: { flexDirection: "row", flexWrap: "wrap", gap: 8, paddingTop: 5 },
  threadLink: { minHeight: 30, flexDirection: "row", alignItems: "center", gap: 4, borderWidth: 1, borderColor: "#BFC7C0", paddingHorizontal: 8 },
  threadLinkText: { fontSize: 11, lineHeight: 16, fontWeight: "700", color: "#355C7D" },
  rankingBlock: { borderLeftWidth: 3, borderLeftColor: "#355C7D", paddingLeft: 12, paddingVertical: 10, gap: 4 },
  scoreRow: { minHeight: 25, flexDirection: "row", alignItems: "center", gap: 8 },
  scoreLabel: { width: 128, fontSize: 11, lineHeight: 16, color: "#59655D" },
  scoreTrack: { flex: 1, height: 5, backgroundColor: "#D8DDD7", overflow: "hidden" },
  scoreFill: { height: 5, backgroundColor: "#355C7D" },
  scoreValue: { width: 34, textAlign: "right", fontSize: 11, lineHeight: 16, color: "#354139" },
  observationCount: { fontSize: 15, lineHeight: 22, fontWeight: "700", color: "#2D6A4F", paddingVertical: 6 },
  calibrationGroup: { borderBottomWidth: 1, borderBottomColor: "#D8DDD7", paddingVertical: 8, gap: 4 },
  calibrationLabel: { fontSize: 12, lineHeight: 18, fontWeight: "700", color: "#354139" },
  valueRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  valueName: { fontSize: 13, lineHeight: 19, color: "#59655D" },
  valueNumber: { fontSize: 13, lineHeight: 19, fontWeight: "700", color: "#17211B" },
  empty: { paddingVertical: 12, fontSize: 13, lineHeight: 20, color: "#59655D" },
  loading: { textAlign: "center", paddingVertical: 8, fontSize: 13, color: "#355C7D" },
});
