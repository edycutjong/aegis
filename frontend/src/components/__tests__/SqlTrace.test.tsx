import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import SqlTrace, { highlightSql } from "../SqlTrace";

describe("SqlTrace", () => {
    it("renders nothing without attempts", () => {
        const { container } = render(<SqlTrace attempts={[]} />);
        expect(container).toBeEmptyDOMElement();
    });

    it("shows every attempt with its outcome and the self-heal count", () => {
        render(
            <SqlTrace
                attempts={[
                    { query: "SELECT * FROM auth.users", error: "Blocked by SQL guard: schema 'auth' is not allowed", rows: null },
                    { query: "SELECT nme FROM customers", error: "column nme does not exist", rows: null },
                    { query: "SELECT name FROM customers WHERE id = 8", error: null, rows: 1 },
                    { query: "SELECT * FROM billing", error: null, rows: 4 },
                    { query: "SELECT 1", error: null, rows: null },
                ]}
            />
        );
        expect(screen.getByText(/5 attempts · 1 blocked by guard/)).toBeInTheDocument();
        expect(screen.getByText("SQL guard blocked")).toBeInTheDocument();
        expect(screen.getByText(/schema 'auth' is not allowed/)).toHaveClass("sql-error-guard");
        expect(screen.getByText("Failed")).toBeInTheDocument();
        expect(screen.getByText("column nme does not exist")).not.toHaveClass("sql-error-guard");
        expect(screen.getByText("Self-heal 1/3")).toBeInTheDocument();
        expect(screen.getByText("1 row")).toBeInTheDocument();
        expect(screen.getByText("4 rows")).toBeInTheDocument();
        expect(screen.getByText("Running…")).toBeInTheDocument();
    });

    it("uses the singular for one attempt with no guard blocks", () => {
        render(<SqlTrace attempts={[{ query: "SELECT 1", error: null, rows: 0 }]} />);
        expect(screen.getByText("1 attempt")).toBeInTheDocument();
    });

    it("highlights keywords, strings and numbers", () => {
        const { container } = render(<code>{highlightSql("select name from customers where plan = 'pro' limit 5")}</code>);
        expect(container.querySelectorAll(".sql-kw")).toHaveLength(4);
        expect(container.querySelector(".sql-str")).toHaveTextContent("'pro'");
        expect(container.querySelector(".sql-num")).toHaveTextContent("5");
        expect(container).toHaveTextContent("select name from customers where plan = 'pro' limit 5");
    });
});
