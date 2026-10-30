# SO'M/QV ikki o'tishli assembler

SO'M/QV (SIC/XE) mashinasi uchun assembler. Python 3, tashqi kutubxonasiz.

```
python3 somasm.py examples/copy.asm            # copy.obj va copy.lst yaratadi
python3 somasm.py dastur.asm -o d.obj -l d.lst
```

- **1-o'tish:** manzillar hisoblanadi, nomlar jadvali (SYMTAB) va literallar to'plami tuziladi.
- **2-o'tish:** ob'ekt kod hosil qilinadi, H/D/R/T/M/E yozuvlari chiqariladi.

Qo'llab-quvvatlanadi: 1-4 formatlar, `#` bevosita, `@` vositali, `,X` indeksli,
PC va BASE nisbiy adreslash, `+` (4-format), literallar (`=C'..'`, `=X'..'`),
`START END BYTE WORD RESB RESW BASE NOBASE LTORG EQU ORG CSECT EXTDEF EXTREF`,
ifodalar (`+ - * /`, masalan `BUFEND-BUFFER`).

Manba format: nishon 1-ustundan boshlanadi; buyruq va operand bo'sh joy bilan ajratiladi;
`.` bilan boshlangan qator izoh. Xatolar listingda `***** XATO` ko'rinishida chiqadi.
