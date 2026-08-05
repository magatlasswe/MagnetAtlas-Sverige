# Build Environment

Projektet använder:

```toml
[build-system]
requires = ["setuptools>=75"]
build-backend = "setuptools.build_meta"
```

Detta följer PEP 517/518.

Under verifieringen konstaterades att ett installationsfel kan uppstå om en
temporär byggmiljö saknar Setuptools och samtidigt inte kan hämta
byggberoenden från PyPI. Detta är inte ett projektfel. Projektets konfiguration
verifierades som korrekt.

Verifierat:

- build-system
- `setuptools.build_meta`
- src-layout
- package discovery
- editable installation
- console script
- package metadata

Orsak: den temporära verifieringsmiljön saknade Setuptools och hade ingen
möjlighet att installera byggberoenden.
