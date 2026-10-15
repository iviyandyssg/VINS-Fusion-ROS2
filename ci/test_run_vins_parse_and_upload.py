#!/usr/bin/env python3
# ci/parse_and_upload.py
"""
解析 pytest JUnit XML，上报 SquashTM。
环境变量：SQUASH_TM_URL / SQUASH_TM_API_TOKEN / SQUASH_TM_ITERATION_ID
可选：RESULTS_XML（默认 reports/results.xml）、DRY_RUN=1
"""

import os
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import requests


@dataclass
class TestResult:
    classname: str
    name: str
    status: str          # passed / failed / error / skipped
    duration: float      # 秒
    message: str = ""


def parse_junit_xml(path: str) -> list[TestResult]:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"找不到测试报告: {path}")

    root = ET.parse(path).getroot()
    suites = root.findall("testsuite") if root.tag == "testsuites" else [root]

    results = []
    for suite in suites:
        for case in suite.findall("testcase"):
            failure = case.find("failure")
            error = case.find("error")
            skipped = case.find("skipped")

            if failure is not None:
                status, msg = "failed", (failure.get("message") or "")
            elif error is not None:
                status, msg = "error", (error.get("message") or "")
            elif skipped is not None:
                status, msg = "skipped", ""
            else:
                status, msg = "passed", ""

            results.append(TestResult(
                classname=case.get("classname", ""),
                name=case.get("name", ""),
                status=status,
                duration=float(case.get("time", "0") or 0),
                message=msg,
            ))
    return results


# ---------- 用例名映射（你需要按实际情况改）----------

def squash_case_key(result: TestResult) -> str:
    """
    把 pytest 用例名映射成 SquashTM 能识别的 key。
    示例名：test_vins[20261012_034525_726153_direct-rectangle-001_87599523]

    方案 A：直接用完整 name（如果 SquashTM 用例名就是它）
    方案 B：取参数化 ID 里的某段，如时间戳或 dataset 名
    方案 C：在 pytest 里给用例打 marker，这里读 marker（需要改 XML 生成方式）

    这里先返回完整 name，你按实际改。
    """
    # return result.name
    # base_name = result.name.split("[")[0]
    # return f"{base_name.upper()}"
    return "TEST_VINS"


# ---------- 上报（endpoint 待你确认）----------

def upload_result(base_url, token, iteration_id, result, dry_run=False):
    key = squash_case_key(result)

    # ⚠️ 下面的 URL 和 payload 是占位，必须按你的 SquashTM 版本 API 改
    # url = f"{base_url.rstrip('/')}/api/rest/latest/iteration/{iteration_id}/automated-test-case"
    # payload = {
    #     "testCaseName": key,
    #     "status": result.status,
    #     "duration": int(result.duration * 1000),
    #     "message": result.message[:1000],
    # }
    url = f"{base_url.rstrip('/')}/api/rest/latest/import/results/{iteration_id}"
    test_results = [
        {
            "reference": key,
            "status": result.status,
            "duration": int(result.duration * 1000), #ms
            "failure_details": result.msg,
        }
    ]
    payload = {
        "test": test_results
    }

    if dry_run:
        print(f"[DRY-RUN] POST {url}\n          {payload}")
        return

    resp = requests.post(url, json=payload,
                         headers={
                             "Authorization": f"Bearer {token}",
                             "Content-Type": "application/json",
                             "Accept": "application/json",
                         },
                         timeout=30)
    resp.raise_for_status()
    print(f"[OK] {key} -> {result.status}")


def main() -> int:
    # base_url = os.environ.get(
    #     "SQUASH_TM_URL",
    #     "https://home.ybn.org.cn/"
    # )
    base_url = os.environ["SQUASH_TM_URL"]
    token = os.environ["SQUASH_TM_API_TOKEN"]
    #iteration_id = os.environ["SQUASH_TM_ITERATION_ID"]
    iteration_id = 52
    xml_path = os.environ.get("RESULTS_XML", "reports/results.xml")
    dry_run = os.environ.get("DRY_RUN", "0") == "1"

    results = parse_junit_xml(xml_path)
    print(f"解析到 {len(results)} 个测试结果")

    failed_uploads = 0
    for r in results:
        try:
            upload_result(base_url, token, iteration_id, r, dry_run)
        except requests.HTTPError as e:
            failed_uploads += 1
            body = e.response.text[:300] if e.response else ""
            print(f"[ERROR] 上报 {r.name} 失败: {e} {body}", file=sys.stderr)

    passed = sum(1 for r in results if r.status == "passed")
    print(f"完成：{passed}/{len(results)} passed，上报失败 {failed_uploads}")
    return 0


if __name__ == "__main__":
    sys.exit(main())