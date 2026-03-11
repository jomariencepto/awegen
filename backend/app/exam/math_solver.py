"""
math_solver.py — SymPy-based equation solver for problem_solving exam questions.

Public API:
    try_sympy_solve(raw_eq)           → dict with success, numeric_value, sympy_expr, latex, error
    extract_numeric_from_answer(text) → float | None
    numeric_answers_match(s, c, tol)  → bool
"""
import re

# ---------------------------------------------------------------------------
# Unicode → SymPy-parseable normalization
# ---------------------------------------------------------------------------
_UNICODE_SUBS = [
    ('×', '*'),
    ('÷', '/'),
    ('−', '-'),   # Unicode minus → ASCII hyphen
    ('²', '**2'),
    ('³', '**3'),
    ('π', 'pi'),
    ('∞', 'oo'),
    # Statistics symbols → named SymPy symbols
    ('x̄', 'xbar'),
    ('ȳ', 'ybar'),
    ('μ', 'mu'),
    ('σ', 'sigma'),
    ('α', 'alpha'),
    ('β', 'beta'),
    ('ρ', 'rho'),
    # Whitespace cleanup
    ('\u200b', ''),   # zero-width space
    ('\xa0', ' '),    # non-breaking space
]


def _normalize_unicode(expr: str) -> str:
    """Replace Unicode math characters with SymPy-parseable equivalents."""
    for uni, replacement in _UNICODE_SUBS:
        expr = expr.replace(uni, replacement)

    # √(expr)  →  sqrt(expr)
    expr = re.sub(r'√\(([^)]+)\)', r'sqrt(\1)', expr)
    # √N  →  sqrt(N)
    expr = re.sub(r'√(\d+(?:\.\d+)?)', r'sqrt(\1)', expr)
    # Remaining lone √ (e.g. √x) → sqrt
    expr = expr.replace('√', 'sqrt')

    # Collapse multiple spaces
    expr = re.sub(r' {2,}', ' ', expr).strip()
    return expr


def _strip_equation_wrapper(raw: str) -> str:
    """Remove [EQUATION: ...] OMML wrapper if present."""
    m = re.match(r'\[EQUATION:\s*(.*?)\s*\]$', raw.strip(), re.DOTALL)
    return m.group(1).strip() if m else raw.strip()


def try_sympy_solve(raw_eq: str) -> dict:
    """
    Attempt to solve or evaluate *raw_eq* using SymPy.

    Returns a dict:
        success       : bool
        numeric_value : float | None   (None for symbolic / multi-variable expressions)
        sympy_expr    : str  | None
        latex         : str  | None
        error         : str  | None
    """
    base = {'success': False, 'numeric_value': None,
            'sympy_expr': None, 'latex': None, 'error': None}

    try:
        import sympy

        # 1. Strip OMML wrapper
        eq = _strip_equation_wrapper(raw_eq)
        if not eq:
            base['error'] = 'Empty expression'
            return base

        # 2. Normalize Unicode
        eq = _normalize_unicode(eq)

        # 3. Route: equation (contains '=') vs plain expression
        if '=' in eq:
            lhs_str, rhs_str = eq.split('=', 1)
            lhs_str = lhs_str.strip()
            rhs_str = rhs_str.strip()

            try:
                lhs_expr = sympy.sympify(lhs_str, evaluate=True)
                rhs_expr = sympy.sympify(rhs_str, evaluate=True)
            except Exception as e:
                base['error'] = f'Parse error: {e}'
                return base

            diff = lhs_expr - rhs_expr
            free = diff.free_symbols

            if len(free) == 0:
                # Purely numeric — evaluate rhs
                val = float(rhs_expr.evalf())
                base.update(success=True, numeric_value=val,
                            sympy_expr=str(rhs_expr))
                try:
                    base['latex'] = sympy.latex(rhs_expr)
                except Exception:
                    pass
                base['steps'] = [
                    f"Given: {lhs_str} = {rhs_str}",
                    f"Result: {round(val, 6)}",
                ]
                return base

            if len(free) == 1:
                var = list(free)[0]
                try:
                    solutions = sympy.solve(diff, var)
                except Exception as e:
                    base['error'] = f'Solve error: {e}'
                    return base

                if not solutions:
                    base['error'] = 'No solution found'
                    return base

                sol = solutions[0]
                numeric = None
                try:
                    numeric = float(sol.evalf())
                except Exception:
                    pass

                base.update(success=True, numeric_value=numeric,
                            sympy_expr=f'{var} = {sol}')
                try:
                    base['latex'] = f'{sympy.latex(var)} = {sympy.latex(sol)}'
                except Exception:
                    pass
                steps = [
                    f"Given: {lhs_str} = {rhs_str}",
                    f"Rearranged: {sympy.latex(diff)} = 0",
                    f"Solving for {var}: {var} = {sympy.latex(sol)}",
                ]
                if numeric is not None:
                    steps.append(f"Numeric result: {var} \u2248 {round(numeric, 6)}")
                base['steps'] = steps
                return base

            # Multiple free symbols — symbolic, no numeric answer
            base.update(success=True,
                        error=f'Multiple unknowns ({free}); expression is symbolic')
            return base

        else:
            # Pure expression — evaluate
            try:
                expr_obj = sympy.sympify(eq, evaluate=True)
            except Exception as e:
                base['error'] = f'Parse error: {e}'
                return base

            free = expr_obj.free_symbols
            if free:
                base.update(success=True,
                            error=f'Symbolic variables ({free}); no numeric result')
                return base

            val = float(expr_obj.evalf())
            base.update(success=True, numeric_value=val,
                        sympy_expr=str(expr_obj))
            try:
                base['latex'] = sympy.latex(expr_obj)
            except Exception:
                pass
            base['steps'] = [
                f"Given expression: {eq}",
                f"Simplified: {sympy.latex(expr_obj)}",
                f"Numeric result: {round(val, 6)}",
            ]
            return base

    except Exception as e:
        base['error'] = str(e)
        return base


def extract_numeric_from_answer(student_text: str):
    """
    Extract the last numeric value (int or decimal) from a free-text string.
    Returns float or None.
    """
    if not student_text:
        return None
    # Remove commas used as thousands separators before scanning
    matches = re.findall(r'[-+]?\d+\.?\d*', student_text.replace(',', ''))
    if not matches:
        return None
    try:
        return float(matches[-1])
    except ValueError:
        return None


def verify_equation_holds(equation_str: str) -> bool:
    """
    Return True when *equation_str* is a provably correct numeric identity
    (e.g. ``2+3 = 5``, ``pi = 3.14159...``).

    Returns False for symbolic equations, non-equation expressions, or
    anything SymPy cannot parse.  Never raises.
    """
    try:
        import sympy

        eq = _normalize_unicode(_strip_equation_wrapper(equation_str))
        if '=' not in eq:
            return False

        lhs_str, rhs_str = eq.split('=', 1)
        lhs = sympy.sympify(lhs_str.strip(), evaluate=True)
        rhs = sympy.sympify(rhs_str.strip(), evaluate=True)
        diff = lhs - rhs

        if len(diff.free_symbols) == 0:
            return abs(float(diff.evalf())) < 1e-9
        return False
    except Exception:
        return False


def verify_mutation_is_false(original: str, mutated: str) -> bool:
    """
    Return True when *mutated* is provably NOT a valid identity — i.e. the
    mutation actually broke the equation.

    Falls back to ``mutated != original`` when SymPy cannot decide, so this
    function **never blocks** question generation.
    """
    if mutated == original:
        return False
    try:
        import sympy

        eq = _normalize_unicode(_strip_equation_wrapper(mutated))
        if '=' not in eq:
            return True          # non-equation mutation — accept

        lhs_str, rhs_str = eq.split('=', 1)
        lhs = sympy.sympify(lhs_str.strip(), evaluate=True)
        rhs = sympy.sympify(rhs_str.strip(), evaluate=True)
        diff = lhs - rhs

        if len(diff.free_symbols) == 0:
            # Numeric: mutation is false if diff is non-zero
            return abs(float(diff.evalf())) > 1e-9

        # Symbolic: check if SymPy can simplify diff to non-zero
        simplified = sympy.simplify(diff)
        return simplified != 0
    except Exception:
        # SymPy failed — accept the mutation (don't block generation)
        return mutated != original


def compute_missing_value(equation_str: str, blank_token: str = '_______'):
    """
    Given an equation where one component has been replaced with
    *blank_token*, solve for the blanked value using SymPy.

    Returns ``float`` on success, ``None`` on failure.  Never raises.
    """
    try:
        import sympy

        substituted = equation_str.replace(blank_token, '__blank__')
        eq = _normalize_unicode(_strip_equation_wrapper(substituted))

        blank_sym = sympy.Symbol('__blank__')

        if '=' in eq:
            lhs_str, rhs_str = eq.split('=', 1)
            lhs = sympy.sympify(lhs_str.strip(), evaluate=True)
            rhs = sympy.sympify(rhs_str.strip(), evaluate=True)
            diff = lhs - rhs

            if blank_sym not in diff.free_symbols:
                return None

            solutions = sympy.solve(diff, blank_sym)
            if solutions:
                val = float(solutions[0].evalf())
                if not (val != val):     # reject NaN
                    return val
        else:
            # Pure expression — try to evaluate if no blanks remain
            expr = sympy.sympify(eq, evaluate=True)
            if blank_sym not in expr.free_symbols and len(expr.free_symbols) == 0:
                val = float(expr.evalf())
                if not (val != val):
                    return val
        return None
    except Exception:
        return None


def numeric_answers_match(student_text: str, correct_answer: str,
                          tolerance: float = 0.01) -> bool:
    """
    Return True when the numeric value in *student_text* is within *tolerance*
    of the numeric value in *correct_answer*.  Returns False if either
    extraction yields None.
    """
    student_val = extract_numeric_from_answer(student_text)
    correct_val = extract_numeric_from_answer(correct_answer)
    if student_val is None or correct_val is None:
        return False
    return abs(student_val - correct_val) <= tolerance
