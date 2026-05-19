"""
Test che il lowering del parallelismo a due rami usi due finestre __mn_mem* disgiunte
(senza eseguire la VM Kairos).
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from mnemo.compile import compile_c_to_kairos
from mnemo.c_parse import parse_c
from mnemo.layout_collect import compute_program_mem_layout

ROOT = Path(__file__).resolve().parents[1]
_FIXTURES = ROOT / "tests" / "fixtures"
_PAR_MPS_LAYOUT_STUB = _FIXTURES / "par_mps_layout_stub.c"


def _relpath(*parts: str) -> str:
    return str(ROOT.joinpath(*parts))


class TestParallelTwoRegions(unittest.TestCase):
    def test_ex33_par_branch_args_disjoint(self) -> None:
        k = compile_c_to_kairos(_relpath("c_examples", "ex33_parallel2_fib.c"))
        self.assertIn("par", k)
        # fib_left: regione 0 — __mn_mem0, …; fib_right: stessa S celle, base S
        m0 = re.search(
            r"call fib_left\(([^)]+)\)", k,
        )
        m1 = re.search(
            r"call fib_right\(([^)]+)\)", k,
        )
        self.assertIsNotNone(m0, "manca call fib_left")
        self.assertIsNotNone(m1, "manca call fib_right")
        args0 = [x.strip() for x in m0.group(1).split(",")]
        args1 = [x.strip() for x in m1.group(1).split(",")]
        mem0 = [x for x in args0 if re.fullmatch(r"__mn_mem\d+", x)]
        mem1 = [x for x in args1 if re.fullmatch(r"__mn_mem\d+", x)]
        # B-opt: callee sigs ridotte alle celle toccate (insiemi diversi tra workers).
        # Invariante partizione: tutti gli indici left in [0..S-1], tutti right in [S..2S-1] o shared.
        # Trova S come max(left)+1 (limite inferiore) e verifica right indici >= S oppure == left[i].

        def idx(atom: str) -> int:
            return int(atom.replace("__mn_mem", ""))

        left_idxs = [idx(x) for x in mem0]
        right_idxs = [idx(x) for x in mem1]
        s_lower_bound = (max(left_idxs) + 1) if left_idxs else 0
        for ri in right_idxs:
            self.assertTrue(
                ri >= s_lower_bound or ri in left_idxs,
                f"right idx {ri} deve essere ≥ S ({s_lower_bound}) o shared (in {left_idxs})",
            )

    def test_ex32_parallel_with_worker_and_cont_regions(self) -> None:
        k = compile_c_to_kairos(_relpath("c_examples", "ex32_parallel_with.c"))
        self.assertIn("par", k)
        m0 = re.search(
            r"call worker_side\(([^)]+)\)", k,
        )
        m1 = re.search(
            r"call main_tail\(([^)]+)\)", k,
        )
        self.assertIsNotNone(m0)
        self.assertIsNotNone(m1)
        w_args = [x.strip() for x in m0.group(1).split(",")]
        c_args = [x.strip() for x in m1.group(1).split(",")]
        w_mem = [x for x in w_args if re.fullmatch(r"__mn_mem\d+", x)]
        c_mem = [x for x in c_args if re.fullmatch(r"__mn_mem\d+", x)]
        # B-opt: empty workers touch zero mem cells → no __mn_mem args.
        # Non-empty case: left=__mn_mem0..S-1; right=__mn_mem<S>..<2S-1>.
        if w_mem and c_mem:
            self.assertEqual(c_mem[0], "__mn_mem0")
            self.assertEqual(w_mem[0], "__mn_mem4")

    def test_infer_partition1_reads_through_library_call(self) -> None:
        """`srecv` in mps.h fa `*answer = …`: il layout deve vederlo nel callee."""
        ast = parse_c(str(_PAR_MPS_LAYOUT_STUB))
        layout = compute_program_mem_layout(ast, 4)
        self.assertIn(
            "answer",
            layout.main_partition1_read_logicals,
            "consumer deve propagare *answer anche quando chiama srecv(m, answer)",
        )

    def test_infer_par_shared_struct_field_via_library_helpers(self) -> None:
        """ssend/srecv usano m->payload nel .h: lo slot deve essere condiviso tra i due worker."""
        ast = parse_c(str(_PAR_MPS_LAYOUT_STUB))
        layout = compute_program_mem_layout(ast, 4)
        idx = layout.slot_of.get(("main", "mps__payload"))
        self.assertIsNotNone(idx)
        self.assertIn(
            idx,
            layout.parallel_file_shared_slots,
            "producer e consumer devono vedere lo stesso __mn_mem per il campo payload",
        )


if __name__ == "__main__":
    unittest.main()
