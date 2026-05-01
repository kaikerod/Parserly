import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const token = request.nextUrl.searchParams.get("token");

  if (!token) {
    return redirectToLogin(request, "missing-token");
  }

  const verifyUrl = new URL("/api/v1/auth/verify", normalizedApiBaseUrl());
  verifyUrl.searchParams.set("token", token);

  try {
    const backendResponse = await fetch(verifyUrl, {
      method: "GET",
      headers: {
        Accept: "application/json"
      },
      cache: "no-store"
    });

    if (!backendResponse.ok) {
      return redirectToLogin(request, "invalid-link");
    }

    const response = NextResponse.redirect(new URL("/dashboard", request.url));
    const setCookie = backendResponse.headers.get("set-cookie");

    if (setCookie) {
      response.headers.append("set-cookie", setCookie);
    }

    response.headers.set("cache-control", "no-store");
    return response;
  } catch {
    return redirectToLogin(request, "verify-unavailable");
  }
}

function redirectToLogin(request: NextRequest, reason: string) {
  const loginUrl = new URL("/login", request.url);
  loginUrl.searchParams.set("error", reason);
  return NextResponse.redirect(loginUrl);
}

function normalizedApiBaseUrl() {
  return API_BASE_URL.replace(/\/$/, "");
}
