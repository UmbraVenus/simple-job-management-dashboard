/** Why a request failed: no response at all, an error status, or a 2xx body that is not what the API promises. */
export type ApiErrorKind = 'network' | 'http' | 'invalid_response';

type ApiErrorDetails = Readonly<{
  /** HTTP status; absent for `network`. */
  status?: number;
  /** Error codes per request field, e.g. `{ name: ['duplicate'] }`. */
  fieldCodes?: Readonly<Record<string, readonly string[]>>;
  /** Code of an error about the request as a whole, e.g. `not_found`. */
  detailCode?: string;
}>;

/**
 * The one error type every API call rejects with. It carries the API's stable
 * error codes and never its English messages: display text is chosen by code
 * (see features/jobs/errorCopy.ts).
 */
export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number | null;
  readonly fieldCodes: Readonly<Record<string, readonly string[]>>;
  readonly detailCode: string | null;

  constructor(kind: ApiErrorKind, details: ApiErrorDetails = {}) {
    super(details.status === undefined ? `API request failed (${kind})` : `API request failed (${kind}, ${details.status})`);
    this.name = 'ApiError';
    this.kind = kind;
    this.status = details.status ?? null;
    this.fieldCodes = details.fieldCodes ?? {};
    this.detailCode = details.detailCode ?? null;
  }

  /**
   * @returns The first error code the API gave for a request field, or `null`.
   */
  fieldCode(field: string): string | null {
    return this.fieldCodes[field]?.[0] ?? null;
  }
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

const REQUEST_TIMEOUT_MS = 15_000;

type RequestOptions = Readonly<{
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE';
  /** Sent as JSON. The API answers 415 to any other content type. */
  body?: Readonly<Record<string, unknown>>;
  signal?: AbortSignal;
}>;

/**
 * Call the API and return the parsed JSON body, or `undefined` for a 204.
 *
 * The result is `unknown` on purpose: callers pass it through a decoder
 * (api/decode.ts) instead of asserting a type the network never promised.
 *
 * @param path Relative URL, so the same build works behind any host or port.
 * @throws ApiError for a network failure, a timeout or a non-2xx status. An aborted
 *   request rejects with the browser's own `AbortError`.
 */
export async function request(path: string, options: RequestOptions = {}): Promise<unknown> {
  const { method = 'GET', body, signal } = options;
  const init: RequestInit = { method, headers: { Accept: 'application/json' } };
  if (body !== undefined) {
    init.headers = { ...init.headers, 'Content-Type': 'application/json' };
    init.body = JSON.stringify(body);
  }
  // Give up after a while: a request that never answers would otherwise leave
  // its spinner (or its disabled button) on screen for good.
  const timeout = AbortSignal.timeout(REQUEST_TIMEOUT_MS);
  init.signal = signal === undefined ? timeout : AbortSignal.any([signal, timeout]);

  let response: Response;
  try {
    response = await fetch(path, init);
  } catch (cause) {
    // Cancelled by the caller (the page it was for is gone): not a failure to report.
    if (signal?.aborted) {
      throw cause;
    }
    throw new ApiError('network');
  }

  if (!response.ok) {
    throw new ApiError('http', { status: response.status, ...(await readErrorCodes(response)) });
  }
  if (response.status === 204) {
    return undefined;
  }
  try {
    return await response.json();
  } catch {
    throw new ApiError('invalid_response', { status: response.status });
  }
}

/**
 * Pull the codes out of an error body. The API sends
 * `{"name": [{"message", "code"}]}` for a field and
 * `{"detail": {"message", "code"}}` for the request; nginx (502) and Django's
 * own error pages send HTML, which yields no codes.
 */
async function readErrorCodes(response: Response): Promise<ApiErrorDetails> {
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    return {};
  }
  if (!isRecord(body)) {
    return {};
  }

  const fieldCodes: Record<string, readonly string[]> = {};
  let detailCode: string | undefined;
  for (const [key, value] of Object.entries(body)) {
    if (Array.isArray(value)) {
      const codes = value.map(readCode).filter((code) => code !== undefined);
      if (codes.length > 0) {
        fieldCodes[key] = codes;
      }
    } else if (key === 'detail') {
      detailCode = readCode(value);
    }
  }
  return detailCode === undefined ? { fieldCodes } : { fieldCodes, detailCode };
}

function readCode(item: unknown): string | undefined {
  return isRecord(item) && typeof item.code === 'string' ? item.code : undefined;
}
