#!/usr/bin/env python3
import json, pathlib
OUT=pathlib.Path("data/research/branch-governance.json")
PRIMARY=["main","dev"]
LEGACY=["development","production","reserve","backup"]
SPECIAL_PREFIXES=["automation/","implementation/","research/"]
def main():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps({
      "version":1,
      "language":"ru",
      "policy":{
        "main":"стабильная опубликованная ветка",
        "dev":"основная рабочая ветка автономной разработки",
        "legacy":"исторические/резервные ветки не использовать для новой работы",
        "temporary":"ветки automation/*, implementation/* и research/* считать временными и закрывать после переноса результата"
      },
      "recommended_flow":"dev → проверка → main",
      "protected_roles":PRIMARY,
      "legacy_roles":LEGACY,
      "temporary_prefixes":SPECIAL_PREFIXES,
      "note":"Тулбокс должен сначала проверять состояние веток и не создавать новую ветку без необходимости."
    },ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
if __name__=="__main__": main()
