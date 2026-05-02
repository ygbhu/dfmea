import { Catch, type ArgumentsHost, type ExceptionFilter } from '@nestjs/common';
import { fail } from '@dfmea/shared';
import { normalizeApiError } from './platform-api.error';

type HttpResponse = {
  status(code: number): {
    json(body: unknown): void;
  };
};

type HttpRequest = {
  headers?: Record<string, string | string[] | undefined>;
};

@Catch()
export class ApiExceptionFilter implements ExceptionFilter {
  catch(exception: unknown, host: ArgumentsHost): void {
    const context = host.switchToHttp();
    const response = context.getResponse<HttpResponse>();
    const request = context.getRequest<HttpRequest>();
    const normalized = normalizeApiError(exception);

    response.status(normalized.statusCode).json(
      fail(normalized.envelope, readRequestId(request)),
    );
  }
}

function readRequestId(request: HttpRequest): string | undefined {
  const value = request.headers?.['x-request-id'];

  if (Array.isArray(value)) {
    return value[0];
  }

  return value;
}
