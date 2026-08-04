import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AgentEvent } from "@/lib/api/generated/client";

import { RealtimeClient, type WebSocketLike } from "./socket";

class FakeSocket implements WebSocketLike {
  onclose: WebSocket["onclose"] = null;
  onerror: WebSocket["onerror"] = null;
  onmessage: WebSocket["onmessage"] = null;
  onopen: WebSocket["onopen"] = null;
  readyState: number = WebSocket.OPEN;

  close() {
    this.readyState = WebSocket.CLOSED;
    this.onclose?.call(
      this as unknown as WebSocket,
      new CloseEvent("close"),
    );
  }

  message(value: unknown) {
    this.onmessage?.call(
      this as unknown as WebSocket,
      new MessageEvent("message", { data: JSON.stringify(value) }),
    );
  }
}

function event(sequence: number): AgentEvent {
  return {
    schema_version: 1,
    event_id: `evt-${sequence}`,
    session_id: "session-a",
    turn_id: "turn-a",
    sequence,
    timestamp: "2026-01-01T00:00:00Z",
    type: "status.updated",
    payload: { message: `step ${sequence}` },
    parent_event_id: null,
  };
}

describe("RealtimeClient", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("reissues a one-time ticket and reconnects after the last sequence", async () => {
    const tickets = vi
      .fn()
      .mockResolvedValueOnce({
        ticket: "a".repeat(32),
        session_id: "session-a",
        expires_at: "2026-01-01T00:01:00Z",
        websocket_path: "/api/v1/sessions/session-a/stream",
      })
      .mockResolvedValueOnce({
        ticket: "b".repeat(32),
        session_id: "session-a",
        expires_at: "2026-01-01T00:01:00Z",
        websocket_path: "/api/v1/sessions/session-a/stream",
      });
    const sockets: FakeSocket[] = [];
    const urls: string[] = [];
    const received: AgentEvent[] = [];
    const client = new RealtimeClient({
      api: { createRealtimeTicket: tickets },
      apiBaseUrl: "http://localhost:8000",
      sessionId: "session-a",
      onEvent: (item) => received.push(item),
      onConnectionState: vi.fn(),
      retryDelaysMs: [10],
      websocketFactory: (url) => {
        urls.push(url);
        const socket = new FakeSocket();
        sockets.push(socket);
        return socket;
      },
    });

    client.start();
    await vi.waitFor(() => expect(sockets).toHaveLength(1));
    sockets[0].message({ type: "stream.ready" });
    sockets[0].message(event(1));
    sockets[0].message(event(1));
    expect(received).toHaveLength(1);

    sockets[0].close();
    await vi.advanceTimersByTimeAsync(10);
    await vi.waitFor(() => expect(sockets).toHaveLength(2));

    expect(tickets).toHaveBeenCalledTimes(2);
    expect(urls[0]).toContain("after_sequence=0");
    expect(urls[1]).toContain("after_sequence=1");
    expect(urls[1]).toContain(`ticket=${"b".repeat(32)}`);
    client.stop();
  });

  it("treats heartbeats as transport-only and stops on a fatal stream error", async () => {
    const states = vi.fn();
    const sockets: FakeSocket[] = [];
    const client = new RealtimeClient({
      api: {
        createRealtimeTicket: vi.fn().mockResolvedValue({
          ticket: "a".repeat(32),
          session_id: "session-a",
          expires_at: "2026-01-01T00:01:00Z",
          websocket_path: "/api/v1/sessions/session-a/stream",
        }),
      },
      apiBaseUrl: "http://localhost:8000",
      sessionId: "session-a",
      onEvent: vi.fn(),
      onConnectionState: states,
      retryDelaysMs: [10],
      websocketFactory: () => {
        const socket = new FakeSocket();
        sockets.push(socket);
        return socket;
      },
    });

    client.start();
    await vi.waitFor(() => expect(sockets).toHaveLength(1));
    sockets[0].message({
      type: "stream.heartbeat",
      session_id: "session-a",
      last_sequence: 99,
    });
    expect(client.currentSequence()).toBe(0);
    sockets[0].message({
      type: "stream.error",
      code: "stream_replay_gap",
      message: "The requested event offset is no longer available.",
      reconnectable: false,
      last_sequence: 0,
    });

    expect(states).toHaveBeenCalledWith("fatal", 0);
    await vi.advanceTimersByTimeAsync(20);
    expect(sockets).toHaveLength(1);
  });
});
