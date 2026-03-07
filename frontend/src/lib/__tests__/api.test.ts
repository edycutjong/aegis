import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const API_URL = "http://localhost:8000";

// Mock global fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

// Import after mocking fetch
import {
    startChat,
    getThread,
    approveAction,
    getMetrics,
    clearCache,
    getDbStatus,
    getTableData,
    connectSSE,
    getTraces,
    getTracingStatus,
} from "../api";

describe("api.ts", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    // ── startChat ──
    describe("startChat", () => {
        it("sends POST with message and returns ChatResponse", async () => {
            const mockResponse = { thread_id: "t1", status: "processing", cache_hit: false };
            mockFetch.mockResolvedValue({
                ok: true,
                json: () => Promise.resolve(mockResponse),
            });

            const result = await startChat("test message");

            expect(mockFetch).toHaveBeenCalledWith(`${API_URL}/api/chat`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: "test message" }),
            });
            expect(result).toEqual(mockResponse);
        });

        it("throws on non-ok response", async () => {
            mockFetch.mockResolvedValue({ ok: false, statusText: "Bad Request" });
            await expect(startChat("bad")).rejects.toThrow("Chat failed: Bad Request");
        });
    });

    // ── getThread ──
    describe("getThread", () => {
        it("fetches thread state by ID", async () => {
            const mockThread = { message: "hi", status: "completed", thought_log: [], proposed_action: null, final_response: "done" };
            mockFetch.mockResolvedValue({
                ok: true,
                json: () => Promise.resolve(mockThread),
            });

            const result = await getThread("thread-123");
            expect(mockFetch).toHaveBeenCalledWith(`${API_URL}/api/thread/thread-123`);
            expect(result).toEqual(mockThread);
        });

        it("throws on failure", async () => {
            mockFetch.mockResolvedValue({ ok: false, statusText: "Not Found" });
            await expect(getThread("bad-id")).rejects.toThrow("Thread fetch failed: Not Found");
        });
    });

    // ── approveAction ──
    describe("approveAction", () => {
        it("sends approval with reason", async () => {
            const mockRes = { thread_id: "t1", status: "completed", result: "done" };
            mockFetch.mockResolvedValue({
                ok: true,
                json: () => Promise.resolve(mockRes),
            });

            const result = await approveAction("t1", true, "looks good");
            expect(mockFetch).toHaveBeenCalledWith(`${API_URL}/api/approve/t1`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ approved: true, reason: "looks good" }),
            });
            expect(result).toEqual(mockRes);
        });

        it("sends denial with default empty reason", async () => {
            mockFetch.mockResolvedValue({
                ok: true,
                json: () => Promise.resolve({ thread_id: "t1", status: "completed", result: null }),
            });

            await approveAction("t1", false);
            expect(mockFetch).toHaveBeenCalledWith(`${API_URL}/api/approve/t1`, expect.objectContaining({
                body: JSON.stringify({ approved: false, reason: "" }),
            }));
        });

        it("throws on failure", async () => {
            mockFetch.mockResolvedValue({ ok: false, statusText: "Server Error" });
            await expect(approveAction("t1", true)).rejects.toThrow("Approval failed: Server Error");
        });
    });

    // ── getMetrics ──
    describe("getMetrics", () => {
        it("fetches metrics", async () => {
            const mockMetrics = { agent_metrics: {}, cache_metrics: {} };
            mockFetch.mockResolvedValue({
                ok: true,
                json: () => Promise.resolve(mockMetrics),
            });

            const result = await getMetrics();
            expect(mockFetch).toHaveBeenCalledWith(`${API_URL}/api/metrics`);
            expect(result).toEqual(mockMetrics);
        });

        it("throws on failure", async () => {
            mockFetch.mockResolvedValue({ ok: false, statusText: "Timeout" });
            await expect(getMetrics()).rejects.toThrow("Metrics fetch failed: Timeout");
        });
    });

    // ── getTraces ──
    describe("getTraces", () => {
        it("fetches traces", async () => {
            const mockTraces = { traces: [], error: null };
            mockFetch.mockResolvedValue({
                ok: true,
                json: () => Promise.resolve(mockTraces),
            });

            const result = await getTraces();
            expect(mockFetch).toHaveBeenCalledWith(`${API_URL}/api/traces`);
            expect(result).toEqual(mockTraces);
        });

        it("throws on failure", async () => {
            mockFetch.mockResolvedValue({ ok: false, statusText: "Unauthorized" });
            await expect(getTraces()).rejects.toThrow("Traces fetch failed: Unauthorized");
        });
    });

    // ── getTracingStatus ──
    describe("getTracingStatus", () => {
        it("fetches tracing status", async () => {
            const mockStatus = { enabled: true, project: "aegis", connected: true };
            mockFetch.mockResolvedValue({
                ok: true,
                json: () => Promise.resolve(mockStatus),
            });

            const result = await getTracingStatus();
            expect(mockFetch).toHaveBeenCalledWith(`${API_URL}/api/tracing-status`);
            expect(result).toEqual(mockStatus);
        });

        it("throws on failure", async () => {
            mockFetch.mockResolvedValue({ ok: false, statusText: "Server Error" });
            await expect(getTracingStatus()).rejects.toThrow("Tracing status failed: Server Error");
        });
    });

    // ── clearCache ──
    describe("clearCache", () => {
        it("sends DELETE and returns result", async () => {
            mockFetch.mockResolvedValue({
                ok: true,
                json: () => Promise.resolve({ status: "ok", keys_deleted: 5 }),
            });

            const result = await clearCache();
            expect(mockFetch).toHaveBeenCalledWith(`${API_URL}/api/cache`, { method: "DELETE" });
            expect(result).toEqual({ status: "ok", keys_deleted: 5 });
        });

        it("throws on failure", async () => {
            mockFetch.mockResolvedValue({ ok: false, statusText: "Forbidden" });
            await expect(clearCache()).rejects.toThrow("Cache clear failed: Forbidden");
        });
    });

    // ── getDbStatus ──
    describe("getDbStatus", () => {
        it("fetches DB status", async () => {
            const mockDb = { customers: { count: 10 } };
            mockFetch.mockResolvedValue({
                ok: true,
                json: () => Promise.resolve(mockDb),
            });

            const result = await getDbStatus();
            expect(mockFetch).toHaveBeenCalledWith(`${API_URL}/api/db-status`);
            expect(result).toEqual(mockDb);
        });

        it("throws on failure", async () => {
            mockFetch.mockResolvedValue({ ok: false, statusText: "Error" });
            await expect(getDbStatus()).rejects.toThrow("DB status fetch failed: Error");
        });
    });

    // ── getTableData ──
    describe("getTableData", () => {
        it("fetches table rows", async () => {
            const mockData = { table: "customers", rows: [{ id: 1 }] };
            mockFetch.mockResolvedValue({
                ok: true,
                json: () => Promise.resolve(mockData),
            });

            const result = await getTableData("customers");
            expect(mockFetch).toHaveBeenCalledWith(`${API_URL}/api/tables/customers`);
            expect(result).toEqual(mockData);
        });

        it("throws on failure", async () => {
            mockFetch.mockResolvedValue({ ok: false, statusText: "Not Found" });
            await expect(getTableData("bad_table")).rejects.toThrow("Table fetch failed: Not Found");
        });
    });

    // ── connectSSE ──
    describe("connectSSE", () => {
        let listeners: Record<string, (e: unknown) => void>;
        let mockES: { addEventListener: ReturnType<typeof vi.fn>; close: ReturnType<typeof vi.fn> };
        let savedES: any;

        beforeEach(() => {
            listeners = {};
            mockES = {
                addEventListener: vi.fn((event: string, handler: (e: unknown) => void) => {
                    listeners[event] = handler;
                }),
                close: vi.fn(),
            };
            savedES = global.EventSource;
            // @ts-expect-error — mock constructor
            global.EventSource = function (url: string) {
                mockES.addEventListener.mock.calls = [];
                // Store the url so we can assert
                (mockES as Record<string, unknown>)._url = url;
                return mockES;
            };
        });

        afterEach(() => {
            global.EventSource = savedES;
        });

        it("creates EventSource and wires up event listeners", () => {
            const onThought = vi.fn();
            const onApproval = vi.fn();
            const onCompleted = vi.fn();
            const onError = vi.fn();
            const onDisambiguation = vi.fn();

            connectSSE("thread-1", onThought, onApproval, onCompleted, onError, onDisambiguation);

            expect(mockES.addEventListener).toHaveBeenCalledTimes(4);

            // Simulate thought event
            listeners["thought"]({ data: JSON.stringify({ step: "step1" }) });
            expect(onThought).toHaveBeenCalledWith("step1");

            // Simulate approval_required event
            const action = { type: "refund", amount: 49 };
            listeners["approval_required"]({ data: JSON.stringify({ action }) });
            expect(onApproval).toHaveBeenCalledWith(action);
            expect(mockES.close).toHaveBeenCalled();

            mockES.close.mockClear();

            // Simulate completed event (no candidates)
            listeners["completed"]({
                data: JSON.stringify({ response: "done", thought_log: ["s1"], customer_candidates: [] }),
            });
            expect(onCompleted).toHaveBeenCalledWith("done", ["s1"]);
            expect(mockES.close).toHaveBeenCalled();
        });

        it("handles completed event with disambiguation candidates", () => {
            const onCompleted = vi.fn();
            const onDisambiguation = vi.fn();

            connectSSE("t2", vi.fn(), vi.fn(), onCompleted, vi.fn(), onDisambiguation);

            const candidates = [{ id: 1, name: "Alice" }, { id: 2, name: "Bob" }];
            listeners["completed"]({
                data: JSON.stringify({ response: "pick one", thought_log: [], customer_candidates: candidates }),
            });
            expect(onDisambiguation).toHaveBeenCalledWith(candidates, "pick one");
            expect(onCompleted).not.toHaveBeenCalled();
        });

        it("handles error MessageEvent", () => {
            const onError = vi.fn();
            connectSSE("t3", vi.fn(), vi.fn(), vi.fn(), onError);

            const messageEvent = new MessageEvent("error", {
                data: JSON.stringify({ error: "something broke" }),
            });
            listeners["error"](messageEvent);
            expect(onError).toHaveBeenCalledWith("something broke");
            expect(mockES.close).toHaveBeenCalled();
        });

        it("handles non-MessageEvent error (connection lost)", () => {
            const onError = vi.fn();
            connectSSE("t4", vi.fn(), vi.fn(), vi.fn(), onError);

            listeners["error"](new Event("error"));
            expect(onError).toHaveBeenCalledWith("Connection lost");
        });

        it("handles completed without disambiguation callback", () => {
            const onCompleted = vi.fn();
            connectSSE("t5", vi.fn(), vi.fn(), onCompleted, vi.fn());

            const candidates = [{ id: 1, name: "Alice" }];
            listeners["completed"]({
                data: JSON.stringify({ response: "pick", thought_log: [], customer_candidates: candidates }),
            });
            expect(onCompleted).toHaveBeenCalledWith("pick", []);
        });
    });
});

