import type { ErrorEnvelope } from './errors';

export interface ApiSuccessEnvelope<TData> {
  ok: true;
  data: TData;
  requestId?: string;
}

export interface ApiErrorEnvelope {
  ok: false;
  error: ErrorEnvelope;
  requestId?: string;
}

export type ApiResponseEnvelope<TData> = ApiSuccessEnvelope<TData> | ApiErrorEnvelope;

export function ok<TData>(data: TData, requestId?: string): ApiSuccessEnvelope<TData> {
  return {
    ok: true,
    data,
    ...(requestId ? { requestId } : {}),
  };
}

export function fail(error: ErrorEnvelope, requestId?: string): ApiErrorEnvelope {
  return {
    ok: false,
    error,
    ...(requestId ? { requestId } : {}),
  };
}
