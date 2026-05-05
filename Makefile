# Mnemo — repo standalone. La VM Kairos è un altro clone (default: cartella sorella `kairos/`).
MNEMO_ROOT := $(abspath .)
# Esempio: ~/Desktop/mnemo e ~/Desktop/kairos → default ok. Altrimenti: make test KAIROS_ROOT=/path/to/kairos
KAIROS_ROOT ?= $(abspath $(MNEMO_ROOT)/../kairos)
KAIROS_PY := $(KAIROS_ROOT)/venv/bin/python
MNEMO_PY := $(MNEMO_ROOT)/.venv/bin/python

C_FILES := $(sort $(wildcard $(MNEMO_ROOT)/c_examples/*.c))
GCC_COMPAT_FILES := $(sort $(wildcard $(MNEMO_ROOT)/c_examples/gcc_compat/generic_*.c))

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
	@echo "  $(GREEN)make compile$(RESET)       mnemo dump-kairos su c_examples/*.c → .kairos"
	@echo "  $(GREEN)make run FILE=<path>$(RESET)  un solo .c (compila) o .kairos — path relativo a mnemo/"
	@echo "  $(GREEN)make run FILE=... MAIN_ARGC=N$(RESET)  opzionale: sovrascrive argc (come mnemo compile --main-argc N)"
	@echo "  $(GREEN)make test$(RESET)         compile + esegue ogni .kairos (timeout 5s, come make test Kairos)"
	@echo "  $(GREEN)make test-gcc-compat$(RESET) confronto mnemo vs gcc su c_examples/gcc_compat/generic_*.c"
	@echo "  $(GREEN)make test-gcc-compat-stop$(RESET) come sopra ma stop al primo fail"
	@echo "  $(GREEN)make test-unit$(RESET)    unittest Python (parallelismo / lowering, senza VM)"
	@echo "  $(GREEN)make clean-kairos$(RESET) rimuove c_examples/*.kairos"
	@echo "  $(CYAN)Kairos VM$(RESET): $(GREEN)KAIROS_ROOT$(RESET) default $(abspath $(MNEMO_ROOT)/../kairos) → $(GREEN)$(KAIROS_PY)$(RESET)"
	@echo ""

$(MNEMO_PY):
	@command -v python3 >/dev/null || (echo "$(RED)serve python3$(RESET)"; exit 1)
	cd $(MNEMO_ROOT) && python3 -m venv .venv && .venv/bin/pip install -q -e .
	@test -f $(MNEMO_PY)

venv: $(MNEMO_PY)

test-unit: $(MNEMO_PY)
	@cd $(MNEMO_ROOT) && $(MNEMO_PY) -m unittest discover -s tests -p 'test_*.py' -v

compile: $(MNEMO_PY)
	@test -n "$(C_FILES)" || (echo "$(RED)nessun file in c_examples/$(RESET)"; exit 1)
	@for c in $(C_FILES); do \
	  echo "$(CYAN)mnemo dump-kairos $$(basename $$c)$(RESET)"; \
	  $(MNEMO_PY) -m mnemo dump-kairos $$c || exit 1; \
	done

test: compile
	@test -f $(KAIROS_PY) || (echo "$(RED)Manca $(KAIROS_PY). Imposta KAIROS_ROOT sulla root del repo Kairos (venv con python -m src.kairos) o clona kairos accanto a mnemo: ../kairos$(RESET)"; exit 1)
	@$(MAKE) -C $(KAIROS_ROOT) build-release
	@passed=0; failed=0; \
	for c in $(C_FILES); do \
	  k="$${c%.c}.kairos"; \
	  name=$$(basename $$k); \
	  output=$$(cd $(KAIROS_ROOT) && timeout 5s $(KAIROS_PY) -m src.kairos $$k --dump-bytecode 2>&1); \
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
	echo "$(CYAN)Mnemo c_examples:$(RESET) $(GREEN)$$passed PASS$(RESET) / $(RED)$$failed FAIL$(RESET)"; \
	if [ $$failed -gt 0 ]; then exit 1; fi

test-gcc-compat: $(MNEMO_PY)
	@test -n "$(GCC_COMPAT_FILES)" || (echo "$(RED)nessun file generic_*.c in c_examples/gcc_compat/$(RESET)"; exit 1)
	@cd $(MNEMO_ROOT) && $(MNEMO_PY) c_examples/gcc_compat/run_compare.py $(COMPAT_ARGS)

test-gcc-compat-stop: $(MNEMO_PY)
	@test -n "$(GCC_COMPAT_FILES)" || (echo "$(RED)nessun file generic_*.c in c_examples/gcc_compat/$(RESET)"; exit 1)
	@cd $(MNEMO_ROOT) && $(MNEMO_PY) c_examples/gcc_compat/run_compare.py --stop-on-first-fail $(COMPAT_ARGS)

run: $(MNEMO_PY)
ifndef FILE
	$(error Specifica FILE= relativo a questa directory, es.: make run FILE=c_examples/ex01_mul_small.c oppure FILE=c_examples/ex01_mul_small.kairos — senza spazi attorno a =)
endif
	@test -f $(KAIROS_PY) || (echo "$(RED)Manca $(KAIROS_PY). Imposta KAIROS_ROOT sulla root del repo Kairos (venv con python -m src.kairos) o clona kairos accanto a mnemo: ../kairos$(RESET)"; exit 1)
	@$(MAKE) -C $(KAIROS_ROOT) build-release >/dev/null
	@runf="$(abspath $(FILE))"; \
	test -f "$$runf" || (echo "$(RED)file non trovato: $(FILE)$(RESET)"; exit 1); \
	case "$$runf" in \
	  *.c) echo "$(CYAN)mnemo dump-kairos $$(basename $$runf)$(RESET)"; \
	       $(MNEMO_PY) -m mnemo dump-kairos "$$runf" \
	         $$(test -n "$(MAIN_ARGC)" && echo --main-argc $(MAIN_ARGC) || true) || exit 1; \
	       runf="$${runf%.c}.kairos" ;; \
	esac; \
	echo "$(CYAN)Kairos $$(basename $$runf)$(RESET)"; \
	cd $(KAIROS_ROOT) && $(KAIROS_PY) -m src.kairos "$$runf" --dump-bytecode

clean-kairos:
	rm -f $(MNEMO_ROOT)/c_examples/*.kairos
