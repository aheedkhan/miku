CC ?= x86_64-w64-mingw32-gcc
CFLAGS = -O2 -Wall -Wextra -Iinclude -municode -DUNICODE -D_UNICODE
LDFLAGS = -lwinhttp -static

SRC = src/main.c src/util.c src/transport.c src/modules.c
OBJ = $(SRC:.c=.o)
OUT = labrat.exe

.PHONY: all clean test

all: $(OUT)

$(OUT): $(OBJ)
	$(CC) $(OBJ) -o $@ $(LDFLAGS)

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJ) $(OUT)

test:
	cd ../server && python3 run_tests.py
