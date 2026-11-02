CC = gcc
CFLAGS = -O3 -pthread -Wall -Wextra -Isrc
LDFLAGS = -lm

SRC = src/main.c \
      src/approach1_single.c \
      src/approach2_local.c \
      src/approach3_mutex.c \
      src/approach3_batch.c

TARGET = monte_carlo

ifeq ($(OS),Windows_NT)
    TARGET := $(TARGET).exe
    RM = del /Q /F
else
    RM = rm -f
endif

all: $(TARGET)

$(TARGET): $(SRC)
	$(CC) $(CFLAGS) $(SRC) -o $(TARGET) $(LDFLAGS)

clean:
	$(RM) $(TARGET)

.PHONY: all clean
