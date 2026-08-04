# Utveckling

Installera projektet med `python -m pip install -e ".[dev]"`. Kör sedan `pytest`,
`ruff check .` och `black --check .` före en ändring lämnas vidare.

Tester ska använda temporära databaser och mockad HTTP-trafik. Läs även
`AGENTS.md` i projektroten innan du bidrar.
