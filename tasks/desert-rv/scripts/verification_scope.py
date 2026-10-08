#!/usr/bin/env python3
"""Report job scope, not a substitute for native XML/APK evidence validation."""
import os
from pathlib import Path


def report(mode, editmode, playmode, android):
    lines = [f'Verification mode: {mode}', f'EditMode job: {editmode}',
             f'PlayMode job: {playmode}']
    if mode == 'checks-only':
        lines.append('Android APK: NOT_RUN (explicit checks-only selection).')
        passed = editmode == playmode == 'success' and android == 'skipped'
        if android != 'skipped':
            lines.append(f'Unexpected Android job state: {android}')
    elif mode == 'traversal-apk':
        lines.append(f'Android APK job: {android}')
        passed = editmode == playmode == android == 'success'
    else:
        lines.append('Invalid verification mode; scope cannot be certified.')
        passed = False
    lines.extend(['Scope gate: ' + ('PASSED' if passed else 'FAILED'),
                  'Device execution: NOT_RUN.',
                  'Scope is the saved TraversalHarness test package, not the complete game.',
                  'Only the native evidence artifacts certify the executed tests/build.'])
    return passed, '\n\n'.join(lines) + '\n'


def main():
    passed, text = report(os.environ['VERIFICATION_MODE'], os.environ['EDITMODE_RESULT'],
                          os.environ['PLAYMODE_RESULT'], os.environ['ANDROID_RESULT'])
    print(text)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a') as stream:
            stream.write(text)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
