export type PluginLoadErrorCode =
  | 'PLUGIN_DIR_NOT_FOUND'
  | 'PLUGIN_MANIFEST_NOT_FOUND'
  | 'PLUGIN_MANIFEST_INVALID'
  | 'PLUGIN_ID_DUPLICATED'
  | 'PLUGIN_VERSION_INVALID'
  | 'PLUGIN_SCHEMA_NOT_FOUND'
  | 'PLUGIN_HANDLER_NOT_FOUND'
  | 'PLUGIN_REFERENCE_INVALID'
  | 'PLUGIN_REQUIREMENT_UNSATISFIED'
  | 'PLUGIN_DISABLED';

export type PluginLoadErrorDetails = Record<string, unknown>;

export class PluginLoadError extends Error {
  readonly code: PluginLoadErrorCode;
  readonly details: PluginLoadErrorDetails;

  constructor(code: PluginLoadErrorCode, message: string, details: PluginLoadErrorDetails = {}) {
    super(message);
    this.name = 'PluginLoadError';
    this.code = code;
    this.details = details;
    Object.setPrototypeOf(this, PluginLoadError.prototype);
  }
}
