COPY    START   0                     Fayl nusxasini olish
        EXTDEF  BUFFER,BUFEND,LENGTH
        EXTREF  RDREC,WRREC
FIRST   STL     RETADR                qaytish adresini saqlash
CLOOP   +JSUB   RDREC                 Berilganlarni o'qish
        LDA     LENGTH                O'qish tugaganligini aniqlash
        COMP    #0                    EOF (LENGTH=0)
        JEQ     ENDFIL                EOF bo'lsa chiqish
        +JSUB   WRREC                 Berilganlarni yozish
        J       CLOOP                 Takrorlash
ENDFIL  LDA     =C'EOF'               Fayl oxiri belgisini yuklash
        STA     BUFFER
        LDA     #3                    LENGTH=3
        STA     LENGTH
        +JSUB   WRREC                 EOF ni chiqarish
        J       @RETADR               Programmadan chiqish
RETADR  RESW    1
LENGTH  RESW    1                     Yozuv uzunligi
        LTORG
BUFFER  RESB    4096                  Bufer
BUFEND  EQU     *
.
RDREC   CSECT                         Buferga yozuvni o'qish
        EXTREF  BUFFER,LENGTH,BUFEND
        CLEAR   X                     Takrorlanish sanagichi 0
        CLEAR   A
        CLEAR   S
        LDT     MAXLEN
RLOOP   TD      INPUT                 O'qish qurilmasini tekshirish
        JEQ     RLOOP
        RD      INPUT
        COMPR   A,S                   Yozuv tugashini tekshirish
        JEQ     EXIT
        +STCH   BUFFER,X              Buferga belgini yozish
        TIXR    T
        JLT     RLOOP
EXIT    +STX    LENGTH                Yozuv uzunligi
        RSUB
INPUT   BYTE    X'F1'                 O'qish qurilmasi kodi
MAXLEN  WORD    BUFEND-BUFFER
.
WRREC   CSECT                         Buferdagi yozuvni chiqarish
        EXTREF  LENGTH,BUFFER
        CLEAR   X
        +LDT    LENGTH
WLOOP   TD      =X'05'                Yozish qurilmasini tekshirish
        JEQ     WLOOP
        +LDCH   BUFFER,X              Buferdan o'qish
        WD      =X'05'                Belgini yozish
        TIXR    T
        JLT     WLOOP
        RSUB
        END     FIRST
