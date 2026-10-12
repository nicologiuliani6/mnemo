# Mnemo — repo standalone. La VM Kairos è un altro clone (default: cartella sorella `kairos/`).
MNEMO_ROOT := $(abspath .)
# Esempio: ~/Desktop/mnemo e ~/Desktop/kairos → default ok. Altrimenti: make test KAIROS_ROOT=/path/to/kairos
KAIROS_ROOT ?= $(abspath $(MNEMO_ROOT)/../kairos)
KAIROS_PY := $(KAIROS_ROOT)/venv/bin/python
MNEMO_PY := $(MNEMO_ROOT)/.venv/bin/python

C_FILES := $(sort $(wildcard $(MNEMO_ROOT)/tests/c/examples/*.c))
GCC_COMPAT_FILES := $(sort $(wildcard $(MNEMO_ROOT)/tests/c/examples/gcc_compat/generic_*.c))

CYAN := \033[0;36m
GREEN := \033[0;32m
RED := \033[0;31m
RESET := \033[0m

.PHONY: all help venv compile test test-unit test-gcc-compat test-gcc-compat-stop run clean-kairos

all: test-unit test

help:
	@echo ""
	@echo "$(CYAN)Mnemo$(RESET)"
	@echo "  $(GREEN)make venv$(RESET)          python3 -m venv .venv && pip install -e ."
	@echo "  $(GREEN)make compile$(RESET)       mnemo dump-kairos on tests/c/examples/*.c → .kairos"
	@echo "  $(GREEN)make run FILE=<path>$(RESET)  one .c (compiled) or .kairos, path relative to mnemo/"
	@echo "  $(GREEN)make run FILE=... MAIN_ARGC=N$(RESET)  optional: overrides argc (like mnemo compile --main-argc N)"
	@echo "  $(GREEN)make test$(RESET)         compile and run every .kairos (600 s timeout)"
	@echo "  $(GREEN)make test-gcc-compat$(RESET) compare mnemo against gcc on tests/c/examples/gcc_compat/generic_*.c"
	@echo "  $(GREEN)make test-gcc-compat-stop$(RESET) as above, stopping at the first failure"
	@echo "  $(GREEN)make test-unit$(RESET)    Python unit tests (no VM)"
	@echo "  $(GREEN)make clean-kairos$(RESET) remove tests/c/examples/*.kairos"
	@echo "  $(CYAN)Kairos VM$(RESET): $(GREEN)KAIROS_ROOT$(RESET) default $(abspath $(MNEMO_ROOT)/../kairos) → $(GREEN)$(KAIROS_PY)$(RESET)"
	@echo ""

$(MNEMO_PY):
	@command -v python3 >/dev/null || (echo "$(RED)python3 is needed$(RESET)"; exit 1)
	cd $(MNEMO_ROOT) && python3 -m venv .venv && .venv/bin/pip install -q -e .
	@test -f $(MNEMO_PY)

venv: $(MNEMO_PY)

test-unit: $(MNEMO_PY)
	@cd $(MNEMO_ROOT) && $(MNEMO_PY) -m unittest discover -s tests -p 'test_*.py' -v

compile: $(MNEMO_PY)
	@test -n "$(C_FILES)" || (echo "$(RED)no file in tests/c/examples/$(RESET)"; exit 1)
	@for c in $(C_FILES); do \
	  echo "$(CYAN)mnemo dump-kairos $$(basename $$c)$(RESET)"; \
	  $(MNEMO_PY) -m mnemo dump-kairos $$c || exit 1; \
	done

test: compile
	@test -f $(KAIROS_PY) || (echo "$(RED)Missing $(KAIROS_PY). Set KAIROS_ROOT to the root of the Kairos repository (with its venv) or clone kairos next to mnemo: ../kairos$(RESET)"; exit 1)
	@$(MAKE) -C $(KAIROS_ROOT) build-release
	@passed=0; failed=0; \
	for c in $(C_FILES); do \
	  k="$${c%.c}.kairos"; \
	  name=$$(basename $$k); \
	  output=$$(cd $(KAIROS_ROOT) && timeout 600s $(KAIROS_PY) -m src.kairos $$k --dump-bytecode 2>&1); \
	  st=$$?; \
	  if [ $$st -eq 124 ]; then \
	    echo "  $(RED)TIMEOUT$(RESET)  $$name"; \
	    failed=$$((failed+1)); \
	  elif [ $$st -ne 0 ]; then \
	    echo "  $(RED)FAIL$(RESET)  $$name (exit $$st)"; \
	    failed=$$((failed+1)); \
	  elif echo "$$output" | grep -qiE "\\<error\\>|DELOCAL.*errato|stack overflow|assertion|\\[VM\\].*sconosciuta|\\[ERRORE\\]"; then \
	    echo "  $(RED)FAIL$(RESET)  $$name"; \
	    failed=$$((failed+1)); \
	  else \
	    echo "  $(GREEN)PASS$(RESET)  $$name"; \
	    passed=$$((passed+1)); \
	  fi; \
	done; \
	echo ""; \
	echo "$(CYAN)Mnemo examples:$(RESET) $(GREEN)$$passed PASS$(RESET) / $(RED)$$failed FAIL$(RESET)"; \
	if [ $$failed -gt 0 ]; then exit 1; fi

test-gcc-compat: $(MNEMO_PY)
	@test -n "$(GCC_COMPAT_FILES)" || (echo "$(RED)no generic_*.c file in tests/c/examples/gcc_compat/$(RESET)"; exit 1)
	@cd $(MNEMO_ROOT) && $(MNEMO_PY) tests/c/examples/gcc_compat/run_compare.py $(COMPAT_ARGS)

test-gcc-compat-stop: $(MNEMO_PY)
	@test -n "$(GCC_COMPAT_FILES)" || (echo "$(RED)no generic_*.c file in tests/c/examples/gcc_compat/$(RESET)"; exit 1)
	@cd $(MNEMO_ROOT) && $(MNEMO_PY) tests/c/examples/gcc_compat/run_compare.py --stop-on-first-fail $(COMPAT_ARGS)

run: $(MNEMO_PY)
ifndef FILE
	$(error Specifica FILE= relativo a questa directory, es.: make run FILE=tests/c/examples/ex01_mul_small.c oppure FILE=tests/c/examples/ex01_mul_small.kairos — senza spazi attorno a =)
endif
	@test -f $(KAIROS_PY) || (echo "$(RED)Missing $(KAIROS_PY). Set KAIROS_ROOT to the root of the Kairos repository (with its venv) or clone kairos next to mnemo: ../kairos$(RESET)"; exit 1)
	@$(MAKE) -C $(KAIROS_ROOT) build-release >/dev/null
	@runf="$(abspath $(FILE))"; \
	test -f "$$runf" || (echo "$(RED)file not found: $(FILE)$(RESET)"; exit 1); \
	case "$$runf" in \
	  *.c) echo "$(CYAN)mnemo dump-kairos $$(basename $$runf)$(RESET)"; \
	       $(MNEMO_PY) -m mnemo dump-kairos "$$runf" \
	         $$(test -n "$(MAIN_ARGC)" && echo --main-argc $(MAIN_ARGC) || true) || exit 1; \
	       runf="$${runf%.c}.kairos" ;; \
	esac; \
	echo "$(CYAN)Kairos $$(basename $$runf)$(RESET)"; \
	cd $(KAIROS_ROOT) && $(KAIROS_PY) -m src.kairos "$$runf" --dump-bytecode

clean-kairos:
	rm -f $(MNEMO_ROOT)/tests/c/examples/*.kairos
