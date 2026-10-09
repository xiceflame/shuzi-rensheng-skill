#!/bin/bash
printf '%s\n' 'NEEDS_USER_ACTION: copy the following prompt into an approved agent; no task has been executed.'
printf '%s\n' "${SHUZI_PROMPT:-}"
exit 3
