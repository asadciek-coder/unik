#!/usr/bin/env python3
"""SO'M/QV (SIC/XE) uchun ikki o'tishli assembler.

Ishlatish:  python3 somasm.py dastur.asm [-o dastur.obj] [-l dastur.lst]

Qo'llab-quvvatlanadi: 1-4 formatlar, #, @, ,X, +, PC/BASE nisbiy adreslash,
literallar (=C'..', =X'..'), LTORG, EQU, ORG, BASE/NOBASE, CSECT,
EXTDEF/EXTREF, ifodalar (+ - * /), H/D/R/T/M/E yozuvlari.
"""
import argparse
import re
import sys

# mnemonik: (format, opkod)
OPS = {
    'FIX': (1, 0xC4), 'FLOAT': (1, 0xC0), 'HIO': (1, 0xF4), 'NORM': (1, 0xC8),
    'SIO': (1, 0xF0), 'TIO': (1, 0xF8),
    'ADDR': (2, 0x90), 'CLEAR': (2, 0xB4), 'COMPR': (2, 0xA0), 'DIVR': (2, 0x9C),
    'MULR': (2, 0x98), 'RMO': (2, 0xAC), 'SHIFTL': (2, 0xA4), 'SHIFTR': (2, 0xA8),
    'SUBR': (2, 0x94), 'SVC': (2, 0xB0), 'TIXR': (2, 0xB8),
    'ADD': (3, 0x18), 'ADDF': (3, 0x58), 'AND': (3, 0x40), 'COMP': (3, 0x28),
    'COMPF': (3, 0x88), 'DIV': (3, 0x24), 'DIVF': (3, 0x64), 'J': (3, 0x3C),
    'JEQ': (3, 0x30), 'JGT': (3, 0x34), 'JLT': (3, 0x38), 'JSUB': (3, 0x48),
    'LDA': (3, 0x00), 'LDB': (3, 0x68), 'LDCH': (3, 0x50), 'LDF': (3, 0x70),
    'LDL': (3, 0x08), 'LDS': (3, 0x6C), 'LDT': (3, 0x74), 'LDX': (3, 0x04),
    'LPS': (3, 0xD0), 'MUL': (3, 0x20), 'MULF': (3, 0x60), 'OR': (3, 0x44),
    'RD': (3, 0xD8), 'RSUB': (3, 0x4C), 'SSK': (3, 0xEC), 'STA': (3, 0x0C),
    'STB': (3, 0x78), 'STCH': (3, 0x54), 'STF': (3, 0x80), 'STI': (3, 0xD4),
    'STL': (3, 0x14), 'STS': (3, 0x7C), 'STSW': (3, 0xE8), 'STT': (3, 0x84),
    'STX': (3, 0x10), 'SUB': (3, 0x1C), 'SUBF': (3, 0x5C), 'TD': (3, 0xE0),
    'TIX': (3, 0x2C), 'WD': (3, 0xDC),
}
REGS = {'A': 0, 'X': 1, 'L': 2, 'B': 3, 'S': 4, 'T': 5, 'F': 6, 'PC': 8, 'SW': 9}
DIRECTIVES = {'START', 'END', 'BYTE', 'WORD', 'RESB', 'RESW', 'BASE', 'NOBASE',
              'LTORG', 'EQU', 'ORG', 'CSECT', 'EXTDEF', 'EXTREF'}


NO_OPERAND = {'CSECT', 'RSUB', 'LTORG', 'NOBASE', 'FIX', 'FLOAT', 'HIO', 'NORM', 'SIO', 'TIO'}


class AsmError(Exception):
    pass


class Line:
    def __init__(self, num, text):
        self.num, self.text = num, text
        self.label = self.op = self.operand = ''
        self.comment = ''
        self.is_comment = False
        self.loc = None
        self.code = ''
        self.sect = None
        self.errors = []


def parse_line(num, text):
    ln = Line(num, text.rstrip('\n'))
    s = ln.text
    if not s.strip() or s.lstrip().startswith('.'):
        ln.is_comment = True
        return ln
    m = re.match(r'(\S+)?\s*', s)
    if s[0] not in ' \t':
        ln.label = m.group(1)
        rest = s[m.end():]
    else:
        rest = s.lstrip()
    parts = rest.split(None, 1)
    if not parts:
        return ln
    ln.op = parts[0].upper()
    if ln.op in NO_OPERAND:
        ln.comment = parts[1] if len(parts) > 1 else ''
    elif len(parts) > 1:
        r = parts[1]
        # qo'shtirnoq ichidagi bo'sh joylar operandga kiradi
        m = re.match(r"((?:[^\s']|'[^']*')+)\s*(.*)", r)
        ln.operand, ln.comment = (m.group(1), m.group(2)) if m else (r, '')
    return ln


def split_ops(operand):
    return [p.strip() for p in operand.split(',')] if operand else []


def literal_bytes(text):
    """C'..' yoki X'..' ni baytlarga aylantiradi."""
    m = re.fullmatch(r"([CX])'(.*)'", text, re.I)
    if not m:
        raise AsmError(f"noto'g'ri literal: {text}")
    if m.group(1).upper() == 'C':
        return m.group(2).encode('latin-1')
    h = m.group(2)
    if len(h) % 2 or not re.fullmatch(r'[0-9A-Fa-f]*', h):
        raise AsmError(f"noto'g'ri hex: {text}")
    return bytes.fromhex(h)


class Section:
    def __init__(self, name):
        self.name = name
        self.start = 0
        self.length = 0
        self.syms = {}      # nom -> (qiymat, nisbiy_mi)
        self.defs = []
        self.refs = []
        self.lits = {}      # literal -> manzil (None = hali joylanmagan)
        self.first = None
        self.lines = []


class Assembler:
    def __init__(self):
        self.sections = []
        self.errors = []

    # ---------- ifodalar ----------
    def eval_expr(self, sec, expr, loc, pass2=False, mrefs=None):
        """(qiymat, nisbiy_soni) qaytaradi. mrefs: [(ishora, nom)] tashqi nomlar."""
        toks = re.findall(r"\*|[A-Za-z_$][\w$]*|0[xX][0-9A-Fa-f]+|\d+|[-+/()]", expr.replace(' ', ''))
        if ''.join(toks) != expr.replace(' ', ''):
            raise AsmError(f"noto'g'ri ifoda: {expr}")
        pos = 0

        def peek():
            return toks[pos] if pos < len(toks) else None

        def atom():
            nonlocal pos
            t = peek()
            if t is None:
                raise AsmError(f"ifoda tugamagan: {expr}")
            pos += 1
            if t == '(':
                v = add(1)
                if peek() != ')':
                    raise AsmError(f"')' kutilgan: {expr}")
                pos += 1
                return v
            if t == '-':
                v, r, e = atom()
                return -v, -r, [(-s, n) for s, n in e]
            if t == '*':
                return loc, 1, []
            if t[0].isdigit():
                return int(t, 0), 0, []
            u = t.upper()
            if u in sec.refs:
                return 0, 0, [(1, u)]
            if u in sec.syms:
                v, rel = sec.syms[u]
                return v, 1 if rel else 0, []
            if pass2:
                raise AsmError(f"aniqlanmagan nom: {t}")
            return 0, 0, []

        def term():
            nonlocal pos
            v, r, e = atom()
            while peek() in ('*', '/'):
                op = toks[pos]
                pos += 1
                v2, r2, e2 = atom()
                if r or r2 or e or e2:
                    raise AsmError(f"'{op}' nisbiy qiymatlar ustida mumkin emas: {expr}")
                v = v * v2 if op == '*' else (v // v2 if v2 else 0)
            return v, r, e

        def add(_=0):
            nonlocal pos
            v, r, e = term()
            while peek() in ('+', '-'):
                op = toks[pos]
                pos += 1
                v2, r2, e2 = term()
                if op == '+':
                    v, r, e = v + v2, r + r2, e + e2
                else:
                    v, r, e = v - v2, r - r2, e + [(-s, n) for s, n in e2]
            return v, r, e

        v, r, e = add()
        if pos != len(toks):
            raise AsmError(f"ifodada ortiqcha belgi: {expr}")
        if mrefs is not None:
            mrefs.extend(e)
        elif e and pass2:
            raise AsmError(f"tashqi nom bu yerda ishlatilmaydi: {expr}")
        return v, r

    # ---------- 1-o'tish ----------
    def pass1(self, src):
        sec = None
        loc = 0
        for num, text in enumerate(src, 1):
            ln = parse_line(num, text)
            if sec is None and not ln.is_comment and ln.op != 'START':
                sec = Section(ln.label.upper() if ln.label and ln.op == 'CSECT' else '')
                self.sections.append(sec)
                loc = 0
            if ln.is_comment:
                if sec:
                    ln.sect = sec
                    sec.lines.append(ln)
                else:
                    self.pre = getattr(self, 'pre', []) + [ln]
                continue
            try:
                if ln.op == 'START':
                    sec = Section(ln.label.upper())
                    self.sections.append(sec)
                    sec.start = loc = int(ln.operand or '0', 16)
                    ln.loc = loc
                    ln.sect = sec
                    sec.lines.append(ln)
                    continue
                if ln.op == 'CSECT':
                    self.close_section(sec, loc)
                    sec = Section(ln.label.upper())
                    self.sections.append(sec)
                    loc = 0
                ln.sect = sec
                ln.loc = loc
                sec.lines.append(ln)
                if ln.label and ln.op not in ('EQU', 'CSECT', 'START'):
                    self.define(sec, ln.label, loc, True)
                loc = self.advance(sec, ln, loc)
            except AsmError as e:
                ln.errors.append(str(e))
                self.errors.append((num, str(e)))
        if sec is None:
            raise AsmError("dastur bo'sh")
        self.close_section(sec, loc)

    def define(self, sec, label, value, rel):
        label = label.upper()
        if label in sec.syms:
            raise AsmError(f"nom ikki marta aniqlangan: {label}")
        sec.syms[label] = (value, rel)

    def close_section(self, sec, loc):
        loc = self.flush_literals(sec, loc)
        sec.length = loc - sec.start
        if sec.length < 0:
            sec.length = 0

    def flush_literals(self, sec, loc):
        for lit in list(sec.lits):
            if sec.lits[lit] is None:
                sec.lits[lit] = loc
                ll = Line(0, '')
                ll.is_comment = False
                ll.label, ll.op, ll.operand = '*', lit, ''
                ll.loc, ll.sect = loc, sec
                ll.literal = True
                sec.lines.append(ll)
                loc += len(literal_bytes(lit[1:]))
        return loc

    def advance(self, sec, ln, loc):
        op, opd = ln.op, ln.operand
        if op == 'CSECT':
            return loc
        if op in ('END', 'LTORG'):
            return self.flush_literals(sec, loc)
        if op == 'EXTDEF':
            sec.defs += [s.upper() for s in split_ops(opd)]
            return loc
        if op == 'EXTREF':
            sec.refs += [s.upper() for s in split_ops(opd)]
            return loc
        if op in ('BASE', 'NOBASE'):
            return loc
        if op == 'EQU':
            if not ln.label:
                raise AsmError("EQU uchun nishon kerak")
            v, r = self.eval_expr(sec, opd, loc)
            self.define(sec, ln.label, v, r > 0)
            ln.loc = v
            return loc
        if op == 'ORG':
            v, _ = self.eval_expr(sec, opd, loc)
            return v
        if op == 'WORD':
            return loc + 3 * max(1, len(split_ops(opd)))
        if op == 'RESW':
            return loc + 3 * int(self.eval_expr(sec, opd, loc)[0])
        if op == 'RESB':
            return loc + int(self.eval_expr(sec, opd, loc)[0])
        if op == 'BYTE':
            if re.match(r"[CXcx]'", opd):
                return loc + len(literal_bytes(opd))
            return loc + 1
        name = op.lstrip('+')
        if name not in OPS:
            raise AsmError(f"noma'lum buyruq: {op}")
        fmt = OPS[name][0]
        if op.startswith('+'):
            if fmt != 3:
                raise AsmError(f"'+' faqat 3-format buyruqda: {op}")
            fmt = 4
        if opd.startswith('='):
            sec.lits.setdefault(opd.upper() if opd[1].upper() not in 'CX' else opd[0] + opd[1].upper() + opd[2:], None)
        ln.fmt = fmt
        return loc + fmt

    # ---------- 2-o'tish ----------
    def pass2(self):
        for sec in self.sections:
            base = None
            for ln in sec.lines:
                if ln.is_comment or ln.errors:
                    continue
                try:
                    base = self.gen(sec, ln, base)
                except AsmError as e:
                    ln.errors.append(str(e))
                    self.errors.append((ln.num, str(e)))

    def gen(self, sec, ln, base):
        op, opd, loc = ln.op, ln.operand, ln.loc
        ln.mods = []
        ln.data = b''
        ln.reserve = False
        if getattr(ln, 'literal', False):
            ln.data = literal_bytes(op[1:])
            ln.code = ln.data.hex().upper()
            return base
        if op == 'BASE':
            base = self.eval_expr(sec, opd, loc, True)[0]
            return base
        if op == 'NOBASE':
            return None
        if op in ('RESB', 'RESW', 'ORG'):
            ln.reserve = True
            return base
        if op in DIRECTIVES - {'BYTE', 'WORD'}:
            return base
        if op == 'BYTE':
            if re.match(r"[CXcx]'", opd):
                ln.data = literal_bytes(opd[0].upper() + opd[1:])
            else:
                ln.data = bytes([self.eval_expr(sec, opd, loc, True)[0] & 0xFF])
        elif op == 'WORD':
            out = b''
            for i, e in enumerate(split_ops(opd) or ['0']):
                mrefs = []
                v, r = self.eval_expr(sec, e, loc, True, mrefs)
                a = loc + 3 * i
                for s, n in mrefs:
                    ln.mods.append((a, 6, ('+' if s > 0 else '-') + n))
                if r > 0:
                    ln.mods.append((a, 6, '+' + sec.name))
                elif r < 0:
                    ln.mods.append((a, 6, '-' + sec.name))
                out += (v & 0xFFFFFF).to_bytes(3, 'big')
            ln.data = out
        else:
            ln.data = self.encode(sec, ln, base)
        ln.code = ln.data.hex().upper()
        return base

    def encode(self, sec, ln, base):
        op, opd, loc = ln.op, ln.operand, ln.loc
        name = op.lstrip('+')
        fmt, opc = OPS[name]
        if fmt == 1:
            return bytes([opc])
        if fmt == 2:
            args = split_ops(opd)
            vals = []
            for a in args:
                if a.upper() in REGS:
                    vals.append(REGS[a.upper()])
                elif name in ('SHIFTL', 'SHIFTR', 'SVC') and args.index(a) == (1 if name != 'SVC' else 0):
                    vals.append(int(a, 0) - (1 if name != 'SVC' else 0))
                else:
                    raise AsmError(f"noto'g'ri registr: {a}")
            if len(vals) == 1:
                vals.append(0)
            return bytes([opc, vals[0] << 4 | vals[1]])
        # 3/4 format
        n = i = 1
        x = b = p = 0
        e = 1 if op.startswith('+') else 0
        if name == 'RSUB':
            return bytes([opc | 3, 0, 0]) if not e else bytes([opc | 3, 0x10, 0, 0])
        o = opd
        if not o:
            raise AsmError(f"{op} uchun operand kerak")
        if o.upper().endswith(',X'):
            x = 1
            o = o[:-2].strip()
        if o.startswith('#'):
            n, i, o = 0, 1, o[1:]
        elif o.startswith('@'):
            n, i, o = 1, 0, o[1:]
        mrefs = []
        if o.startswith('='):
            key = o[0] + o[1].upper() + o[2:] if o[1].upper() in 'CX' else o.upper()
            ta, rel = sec.lits[key], 1
        else:
            ta, rel = self.eval_expr(sec, o, loc, True, mrefs)
        ext = bool(mrefs)
        immediate_const = (n, i) == (0, 1) and rel == 0 and not ext
        if e:
            disp = ta & 0xFFFFF
            if ext:
                for s, nm in mrefs:
                    ln.mods.append((loc + 1, 5, ('+' if s > 0 else '-') + nm))
            elif rel:
                ln.mods.append((loc + 1, 5, '+' + sec.name))
            return bytes([opc | n << 1 | i, x << 7 | e << 4 | (disp >> 16), (disp >> 8) & 0xFF, disp & 0xFF])
        if ext:
            raise AsmError("tashqi nom uchun 4-format (+) kerak")
        if immediate_const or (rel == 0 and re.fullmatch(r'\d+', o)):
            if not -2048 <= ta <= 4095:
                raise AsmError(f"qiymat 12 razryaddan katta: {ta}")
            disp = ta & 0xFFF
        else:
            pc = loc + 3
            d = ta - pc
            if -2048 <= d <= 2047:
                p, disp = 1, d & 0xFFF
            elif base is not None and 0 <= ta - base <= 4095:
                b, disp = 1, ta - base
            else:
                raise AsmError(f"manzil {ta:X} uchun PC/BASE nisbiy adreslash yetarli emas")
        return bytes([opc | n << 1 | i, x << 7 | b << 6 | p << 5 | e << 4 | (disp >> 8),
                      disp & 0xFF])

    # ---------- chiqish ----------
    def object_program(self, first_exec=None):
        out = []
        for k, sec in enumerate(self.sections):
            out.append(f"H^{sec.name:<6.6}^{sec.start:06X}^{sec.length:06X}")
            if sec.defs:
                out.append('D' + ''.join(f"^{d:<6.6}^{sec.syms[d][0]:06X}" if d in sec.syms
                                         else f"^{d:<6.6}^000000" for d in sec.defs))
            if sec.refs:
                out.append('R' + ''.join(f"^{r:<6.6}" for r in sec.refs))
            cur, cur_start = b'', None
            mods = []
            def flush():
                nonlocal cur, cur_start
                if cur:
                    out.append(f"T^{cur_start:06X}^{len(cur):02X}^{cur.hex().upper()}")
                cur, cur_start = b'', None
            for ln in sec.lines:
                if ln.is_comment or ln.errors:
                    continue
                if ln.reserve:
                    flush()
                    continue
                if not ln.data:
                    continue
                mods += ln.mods
                if cur_start is None:
                    cur_start = ln.loc
                if len(cur) + len(ln.data) > 30:
                    flush()
                    cur_start = ln.loc
                cur += ln.data
            flush()
            for a, hl, sym in mods:
                out.append(f"M^{a:06X}^{hl:02X}^{sym}")
            if k == 0 and first_exec is not None:
                out.append(f"E^{first_exec:06X}")
            else:
                out.append("E")
        return '\n'.join(out) + '\n'

    def listing(self):
        out = []
        for sec in self.sections:
            for ln in sec.lines:
                if ln.is_comment:
                    out.append(f"{ln.num:>5}  {'':<6} {ln.text}")
                    continue
                loc = f"{ln.loc:04X}" if ln.loc is not None else ''
                if getattr(ln, 'literal', False):
                    out.append(f"{'':>5}  {loc:<6} {'*':<8} {ln.op:<8} {'':<12} {ln.code}")
                else:
                    out.append(f"{ln.num:>5}  {loc:<6} {ln.label:<8} {ln.op:<8} "
                               f"{ln.operand:<12} {ln.code:<8} {ln.comment}".rstrip())
                for e in ln.errors:
                    out.append(f"***** XATO: {e}")
        return '\n'.join(out) + '\n'


def assemble(text):
    a = Assembler()
    a.pass1(text.splitlines())
    a.pass2()
    first = None
    for ln in a.sections[0].lines:
        if ln.op == 'END':
            sec0 = a.sections[0]
            try:
                first = a.eval_expr(sec0, ln.operand, 0, True)[0] if ln.operand else sec0.start
            except AsmError as e:
                a.errors.append((ln.num, str(e)))
    return a, first


def main():
    ap = argparse.ArgumentParser(description="SO'M/QV ikki o'tishli assembleri")
    ap.add_argument('source')
    ap.add_argument('-o', '--obj', help='ob\'ekt fayl (standart: <nom>.obj)')
    ap.add_argument('-l', '--lst', help='listing fayl (standart: <nom>.lst)')
    args = ap.parse_args()
    base = re.sub(r'\.\w+$', '', args.source)
    with open(args.source, encoding='utf-8') as f:
        a, first = assemble(f.read())
    lst = a.listing()
    print(lst, end='')
    if a.errors:
        print(f"\n{len(a.errors)} ta xato topildi, ob'ekt fayl yaratilmadi.", file=sys.stderr)
        sys.exit(1)
    obj = a.object_program(first)
    with open(args.obj or base + '.obj', 'w') as f:
        f.write(obj)
    with open(args.lst or base + '.lst', 'w', encoding='utf-8') as f:
        f.write(lst)
    print('\n' + obj, end='')


if __name__ == '__main__':
    main()
