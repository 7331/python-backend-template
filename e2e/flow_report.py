class FlowCheckFailedError(Exception):
    pass


class FlowReport:
    def __init__(self) -> None:
        self.passed_check_count = 0
        self.failed_check_count = 0
        self.check_lines: list[str] = []

    def record_check(self, check_name: str, *, passed: bool, detail: str) -> bool:
        check_line = f"{'PASS' if passed else 'FAIL'} {check_name}: {detail}"
        print(check_line, flush=True)
        self.check_lines.append(check_line)
        if passed:
            self.passed_check_count += 1
        else:
            self.failed_check_count += 1
        return passed

    def require_check(self, check_name: str, *, passed: bool, detail: str) -> None:
        if not self.record_check(check_name, passed=passed, detail=detail):
            raise FlowCheckFailedError(check_name)

    def has_passed(self) -> bool:
        return self.passed_check_count > 0 and self.failed_check_count == 0
