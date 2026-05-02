import Ajv2020 from 'ajv/dist/2020';
import type { ErrorObject, Options, ValidateFunction } from 'ajv';
import addFormats from 'ajv-formats';
import type { ValidationIssue, ValidationResult } from './errors';
import type { JsonObject, JsonSchema, JsonValue } from './json';

export interface JsonSchemaValidator {
  validate(schema: JsonSchema, data: JsonValue): ValidationResult;
  compile(schema: JsonSchema): ValidateFunction;
}

export function createJsonSchemaValidator(options: Options = {}): JsonSchemaValidator {
  const ajv = new Ajv2020({
    allErrors: true,
    strict: true,
    ...options,
  });
  addFormats(ajv);

  return {
    compile(schema) {
      return ajv.compile(schema);
    },
    validate(schema, data) {
      const validate = ajv.compile(schema);
      const valid = validate(data);

      return {
        status: valid ? 'valid' : 'invalid',
        issues: valid ? [] : mapAjvErrors(validate.errors ?? []),
      };
    },
  };
}

function mapAjvErrors(errors: ErrorObject[]): ValidationIssue[] {
  return errors.map((error) => ({
    instancePath: error.instancePath,
    schemaPath: error.schemaPath,
    message: error.message ?? 'JSON schema validation failed',
    keyword: error.keyword,
    params: error.params as JsonObject,
  }));
}
