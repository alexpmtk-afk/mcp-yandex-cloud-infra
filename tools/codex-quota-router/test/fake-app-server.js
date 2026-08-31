#!/usr/bin/env node
'use strict';

let pending = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => {
  pending += chunk;
  for (;;) {
    const nl = pending.indexOf('\n');
    if (nl < 0) break;
    const line = pending.slice(0, nl);
    pending = pending.slice(nl + 1);
    if (line.length) process.stdout.write(line + '\n');
  }
});
process.stdin.on('end', () => {
  if (pending.length) process.stdout.write(pending + '\n');
});
