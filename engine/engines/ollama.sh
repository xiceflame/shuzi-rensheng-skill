#!/bin/bash
# A text-generation endpoint is not a file-writing agent. Fail closed rather
# than report a successful unattended maintenance task without any artifact.
printf '%s\n' '[UNSUPPORTED] Ollama adapter has no verified file-tool loop. Use a sandboxed agent or manual mode.' >&2
exit 4
