import { describe, it, expect } from "vitest";
import { ApiError } from "../api";
import { describeError, formatWait } from "../errors";

describe("describeError", () => {
    it("explains a 429 with the server's detail and retry hint", () => {
        const n = describeError(new ApiError("x", 429, "Easy there.", 120));
        expect(n).toMatchObject({ kind: "rate_limited", detail: "Easy there.", retryAfterSeconds: 120 });
    });

    it("falls back to friendly copy when a 429 has no detail", () => {
        expect(describeError(new ApiError("x", 429)).detail).toMatch(/Give it a minute/);
    });

    it("treats status 0 as the backend being unreachable", () => {
        expect(describeError(new ApiError("x", 0)).kind).toBe("offline");
    });

    it.each([400, 422])("reports %i as a rejected ticket", (status) => {
        expect(describeError(new ApiError("x", status, "too long")).detail).toBe("too long");
        expect(describeError(new ApiError("x", status)).kind).toBe("rejected");
        expect(describeError(new ApiError("x", status)).detail).toMatch(/1,000 characters/);
    });

    it("reports other statuses as server errors", () => {
        expect(describeError(new ApiError("boom", 500, "db down")).detail).toBe("db down");
        expect(describeError(new ApiError("boom", 500)).detail).toBe("boom");
    });

    it("handles plain errors and non-errors", () => {
        expect(describeError(new Error("nope")).detail).toBe("nope");
        expect(describeError("weird").detail).toBe("weird");
    });
});

describe("formatWait", () => {
    it("formats seconds, minutes and hours", () => {
        expect(formatWait(45)).toBe("45s");
        expect(formatWait(120)).toBe("2m");
        expect(formatWait(200)).toBe("3m 20s");
        expect(formatWait(7260)).toBe("2h 1m");
        expect(formatWait(3600)).toBe("1h");
    });
});

