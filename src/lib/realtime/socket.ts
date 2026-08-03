import type { SandboxApi } from "@/lib/api/client";
import type { AgentEvent } from "@/lib/api/generated/client";

export type RealtimeConnectionState =
  | "connecting"
  | "connected"
  | "offline"
  | "fatal";

export type WebSocketLike = Pick<
  WebSocket,
  "close" | "onclose" | "onerror" | "onmessage" | "onopen" | "readyState"
>;

export type RealtimeClientOptions = {
  api: Pick<SandboxApi, "createRealtimeTicket">;
  apiBaseUrl: string;
  sessionId: string;
  afterSequence?: number;
  onEvent: (event: AgentEvent) => void;
  onConnectionState: (
    state: RealtimeConnectionState,
    reconnectAttempt: number,
  ) => void;
  websocketFactory?: (url: string) => WebSocketLike;
  retryDelaysMs?: readonly number[];
};

function defaultWebSocketFactory(url: string): WebSocketLike {
  return new WebSocket(url);
}

function isAgentEvent(value: unknown): value is AgentEvent {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return (
    record.schema_version === 1 &&
    typeof record.event_id === "string" &&
    typeof record.session_id === "string" &&
    typeof record.turn_id === "string" &&
    typeof record.sequence === "number" &&
    typeof record.type === "string" &&
    Boolean(record.payload) &&
    typeof record.payload === "object"
  );
}

export class RealtimeClient {
  private readonly options: RealtimeClientOptions;
  private readonly websocketFactory: (url: string) => WebSocketLike;
  private readonly retryDelaysMs: readonly number[];
  private socket: WebSocketLike | undefined;
  private retryTimer: ReturnType<typeof setTimeout> | undefined;
  private running = false;
  private opening = false;
  private reconnectAttempt = 0;
  private lastSequence: number;

  constructor(options: RealtimeClientOptions) {
    this.options = options;
    this.websocketFactory = options.websocketFactory ?? defaultWebSocketFactory;
    this.retryDelaysMs = options.retryDelaysMs ?? [250, 500, 1_000, 2_000, 4_000];
    this.lastSequence = options.afterSequence ?? 0;
  }

  start(): void {
    if (this.running) return;
    this.running = true;
    void this.open();
  }

  stop(): void {
    this.running = false;
    if (this.retryTimer) clearTimeout(this.retryTimer);
    this.retryTimer = undefined;
    this.socket?.close(1000, "Client stopped.");
    this.socket = undefined;
  }

  currentSequence(): number {
    return this.lastSequence;
  }

  private async open(): Promise<void> {
    if (!this.running || this.opening) return;
    this.opening = true;
    this.options.onConnectionState("connecting", this.reconnectAttempt);
    try {
      const issued = await this.options.api.createRealtimeTicket({
        session_id: this.options.sessionId,
      });
      if (!this.running) return;
      const base = new URL(this.options.apiBaseUrl);
      base.protocol = base.protocol === "https:" ? "wss:" : "ws:";
      const url = new URL(issued.websocket_path, base);
      url.searchParams.set("ticket", issued.ticket);
      url.searchParams.set("after_sequence", String(this.lastSequence));
      const socket = this.websocketFactory(url.toString());
      this.socket = socket;
      socket.onopen = () => {
        this.reconnectAttempt = 0;
      };
      socket.onmessage = (message) => this.onMessage(message.data);
      socket.onerror = () => socket.close();
      socket.onclose = () => {
        if (this.socket === socket) this.socket = undefined;
        if (this.running) this.scheduleReconnect();
      };
    } catch {
      if (this.running) this.scheduleReconnect();
    } finally {
      this.opening = false;
    }
  }

  private onMessage(serialized: unknown): void {
    if (typeof serialized !== "string") return;
    let payload: unknown;
    try {
      payload = JSON.parse(serialized);
    } catch {
      return;
    }
    if (
      payload &&
      typeof payload === "object" &&
      (payload as { type?: unknown }).type === "stream.ready"
    ) {
      this.options.onConnectionState("connected", 0);
      return;
    }
    if (!isAgentEvent(payload) || payload.session_id !== this.options.sessionId) {
      return;
    }
    if (payload.sequence <= this.lastSequence) return;
    if (payload.sequence !== this.lastSequence + 1) {
      this.socket?.close(4000, "Event sequence gap.");
      return;
    }
    this.lastSequence = payload.sequence;
    this.options.onEvent(payload);
  }

  private scheduleReconnect(): void {
    this.reconnectAttempt += 1;
    if (this.reconnectAttempt > this.retryDelaysMs.length) {
      this.options.onConnectionState("fatal", this.reconnectAttempt);
      this.running = false;
      return;
    }
    this.options.onConnectionState("offline", this.reconnectAttempt);
    this.retryTimer = setTimeout(
      () => void this.open(),
      this.retryDelaysMs[this.reconnectAttempt - 1],
    );
  }
}
