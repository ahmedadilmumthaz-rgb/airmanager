import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const BACKEND_BASE =
  process.env.AIRMANAGER_BACKEND_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8001";

async function proxyToBackend(
  req: NextRequest,
  context: { params: { path: string[] } }
): Promise<NextResponse> {
  const subPath = (context.params.path || []).join("/");
  const search = req.nextUrl.search || "";
  const targetUrl = `${BACKEND_BASE.replace(/\/$/, "")}/api/v1/${subPath}${search}`;

  const headers = new Headers();
  req.headers.forEach((value, key) => {
    const k = key.toLowerCase();
    if (k !== "host" && k !== "connection" && k !== "content-length") {
      headers.set(key, value);
    }
  });

  const init: RequestInit = {
    method: req.method,
    headers,
    cache: "no-store",
  };

  if (req.method !== "GET" && req.method !== "HEAD") {
    const bodyText = await req.text();
    if (bodyText) {
      init.body = bodyText;
    }
  }

  try {
    const upstream = await fetch(targetUrl, init);
    const respText = await upstream.text();
    return new NextResponse(respText, {
      status: upstream.status,
      headers: {
        "Content-Type": upstream.headers.get("Content-Type") || "application/json",
      },
    });
  } catch (err) {
    return NextResponse.json(
      {
        detail: `Backend unreachable at ${targetUrl}: ${
          err instanceof Error ? err.message : String(err)
        }`,
      },
      { status: 502 }
    );
  }
}

export async function GET(req: NextRequest, ctx: { params: { path: string[] } }) {
  return proxyToBackend(req, ctx);
}

export async function POST(req: NextRequest, ctx: { params: { path: string[] } }) {
  return proxyToBackend(req, ctx);
}

export async function PUT(req: NextRequest, ctx: { params: { path: string[] } }) {
  return proxyToBackend(req, ctx);
}

export async function DELETE(req: NextRequest, ctx: { params: { path: string[] } }) {
  return proxyToBackend(req, ctx);
}
