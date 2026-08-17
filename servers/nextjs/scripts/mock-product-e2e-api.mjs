import http from "node:http";

const SESSION_COOKIE = "bayanly_e2e_session";
const workspace = {
  id: "10000000-0000-4000-8000-000000000001",
  name: "Personal",
  isPersonal: true,
  role: "OWNER",
  permissions: [
    "workspace:view",
    "members:view",
    "presentations:read",
    "presentations:write",
  ],
  createdAt: "2026-01-01T00:00:00.000Z",
};

function presentation(id, title, createdAt = "2026-06-01T09:00:00.000Z") {
  return {
    id,
    version: "v2-standard",
    title,
    created_at: createdAt,
    updated_at: createdAt,
    data: null,
    file: "",
    n_slides: 10,
    prompt: "A concise product strategy presentation",
    summary: null,
    theme: null,
    titles: [],
    user_id: "e2e-user",
    vector_store: null,
    thumbnail: "",
    slides: [],
  };
}

let presentations = [];

function resetState() {
  presentations = [presentation("presentation-1", "Quarterly Strategy")];
}

function json(response, status, payload, headers = {}) {
  response.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
    ...headers,
  });
  response.end(JSON.stringify(payload));
}

function isAuthenticated(request) {
  return (request.headers.cookie || "")
    .split(";")
    .some((item) => item.trim() === `${SESSION_COOKIE}=user`);
}

async function readJson(request) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  const body = Buffer.concat(chunks).toString("utf8");
  return body ? JSON.parse(body) : {};
}

function requireSession(request, response) {
  if (isAuthenticated(request)) return true;
  json(response, 401, { detail: "Unauthorized" });
  return false;
}

export function createMockProductApiServer() {
  resetState();
  return http.createServer(async (request, response) => {
    const url = new URL(request.url || "/", "http://127.0.0.1");
    const pathname = url.pathname;

    try {
      if (request.method === "POST" && pathname === "/__test/reset") {
        resetState();
        json(response, 200, { ok: true }, {
          "set-cookie": `${SESSION_COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax`,
        });
        return;
      }

      if (request.method === "GET" && pathname === "/api/v1/auth/status") {
        const authenticated = isAuthenticated(request);
        json(response, 200, {
          configured: true,
          authenticated,
          username: authenticated ? "Ayman" : null,
          user_id: authenticated ? "e2e-user" : null,
          role: authenticated ? "user" : null,
          preferred_locale: null,
        });
        return;
      }

      if (request.method === "POST" && pathname === "/api/v1/auth/login") {
        const payload = await readJson(request);
        if (typeof payload.username !== "string" || typeof payload.password !== "string") {
          json(response, 422, { detail: "Invalid credentials" });
          return;
        }
        json(response, 200, {
          configured: true,
          authenticated: true,
          username: payload.username,
          user_id: "e2e-user",
          role: "user",
        }, {
          "set-cookie": `${SESSION_COOKIE}=user; Path=/; HttpOnly; SameSite=Lax`,
        });
        return;
      }

      if (request.method === "POST" && pathname === "/api/v1/auth/logout") {
        json(response, 200, { authenticated: false }, {
          "set-cookie": `${SESSION_COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax`,
        });
        return;
      }

      if (request.method === "PUT" && pathname === "/api/v1/auth/preferences/locale") {
        if (!requireSession(request, response)) return;
        json(response, 200, await readJson(request));
        return;
      }

      if (pathname === "/api/v1/workspaces" && request.method === "GET") {
        if (!requireSession(request, response)) return;
        json(response, 200, [workspace]);
        return;
      }

      if (pathname === "/api/v1/workspaces/current" && request.method === "GET") {
        if (!requireSession(request, response)) return;
        json(response, 200, workspace);
        return;
      }

      if (pathname === "/api/v1/workspaces/current" && request.method === "PUT") {
        if (!requireSession(request, response)) return;
        json(response, 200, workspace);
        return;
      }

      if (pathname === "/api/v1/ppt/presentation/all" && request.method === "GET") {
        if (!requireSession(request, response)) return;
        json(response, 200, url.searchParams.get("version") === "v1-standard" ? [] : presentations);
        return;
      }

      if (pathname === "/api/v1/ppt/presentation/create" && request.method === "POST") {
        if (!requireSession(request, response)) return;
        const payload = await readJson(request);
        json(response, 200, { id: "outline-handoff", ...payload });
        return;
      }

      if (pathname === "/api/v1/ppt/presentation/create/blank" && request.method === "POST") {
        if (!requireSession(request, response)) return;
        const created = presentation("blank-presentation", "Untitled presentation");
        presentations.unshift(created);
        json(response, 200, created);
        return;
      }

      const duplicateMatch = pathname.match(/^\/api\/v1\/ppt\/presentation\/([^/]+)\/duplicate$/);
      if (duplicateMatch && request.method === "POST") {
        if (!requireSession(request, response)) return;
        const source = presentations.find((item) => item.id === duplicateMatch[1]);
        if (!source) {
          json(response, 404, { detail: "Presentation not found" });
          return;
        }
        const duplicated = {
          ...source,
          id: `${source.id}-copy`,
          title: `${source.title} Copy`,
          updated_at: "2026-06-02T09:00:00.000Z",
        };
        presentations.unshift(duplicated);
        json(response, 200, duplicated);
        return;
      }

      const presentationMatch = pathname.match(/^\/api\/v1\/ppt\/presentation\/([^/]+)$/);
      if (presentationMatch && request.method === "GET") {
        if (!requireSession(request, response)) return;
        const found = presentations.find((item) => item.id === presentationMatch[1]);
        json(response, found ? 200 : 404, found || { detail: "Presentation not found" });
        return;
      }

      if (presentationMatch && request.method === "DELETE") {
        if (!requireSession(request, response)) return;
        presentations = presentations.filter((item) => item.id !== presentationMatch[1]);
        response.writeHead(204);
        response.end();
        return;
      }

      json(response, 404, { detail: `No E2E fake for ${request.method} ${pathname}` });
    } catch (error) {
      json(response, 500, { detail: error instanceof Error ? error.message : "Mock API error" });
    }
  });
}

