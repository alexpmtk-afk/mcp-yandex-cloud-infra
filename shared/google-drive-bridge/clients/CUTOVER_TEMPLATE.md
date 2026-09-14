# Client cutover template

## Before
- current bridge URL: `<legacy>`
- current secret source: `<legacy>`
- current root: `<legacy>`

## After
- project id: `<project>`
- bridge protocol: `1`
- project-specific bridge URL: `<new>`
- project-specific Lockbox binding: `<new>`
- fixed root: `<new>`

## Verification
- deep health PASS
- security negative tests PASS
- project transport acceptance PASS
- rollback reference retained

## Decommission
Remove old shared URL/secret binding only after post-cutover verification.
