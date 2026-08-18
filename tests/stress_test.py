import asyncio
import argparse
import json
import sys
import time
import tracemalloc
import statistics
import urllib.request
import urllib.error
from datetime import datetime

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class StressTestReport:
    def __init__(self):
        self.concurrent_results = {}
        self.memory_results = {}
        self.abnormal_results = {}
        self.start_time = datetime.now()

    def to_dict(self):
        return {
            "test_time": self.start_time.isoformat(),
            "duration_seconds": (datetime.now() - self.start_time).total_seconds(),
            "concurrent_test": self.concurrent_results,
            "memory_test": self.memory_results,
            "abnormal_input_test": self.abnormal_results,
        }

    def print_report(self):
        print("\n" + "=" * 70)
        print("  压力测试报告")
        print("=" * 70)
        print(f"  测试时间: {self.start_time.isoformat()}")
        print(f"  测试时长: {(datetime.now() - self.start_time).total_seconds():.2f}秒")

        print("\n" + "-" * 70)
        print("  1. 并发访问测试结果")
        print("-" * 70)
        for concurrency, result in self.concurrent_results.items():
            print(f"\n  并发数: {concurrency}")
            if "error" in result:
                print(f"    错误: {result['error']}")
            else:
                print(f"    总请求数: {result['total_requests']}")
                print(f"    成功数: {result['success_count']}")
                print(f"    失败数: {result['fail_count']}")
                print(f"    成功率: {result['success_rate']:.1f}%")
                print(f"    平均响应时间: {result['avg_time']:.3f}秒")
                print(f"    最小响应时间: {result['min_time']:.3f}秒")
                print(f"    最大响应时间: {result['max_time']:.3f}秒")
                print(f"    中位数响应时间: {result['median_time']:.3f}秒")
                if result.get("errors"):
                    print(f"    错误详情: {result['errors'][:3]}")

        print("\n" + "-" * 70)
        print("  2. 内存泄漏测试结果")
        print("-" * 70)
        if "error" in self.memory_results:
            print(f"    错误: {self.memory_results['error']}")
        else:
            print(f"    总请求数: {self.memory_results['total_requests']}")
            print(f"    初始内存: {self.memory_results['initial_memory_mb']:.2f}MB")
            print(f"    最终内存: {self.memory_results['final_memory_mb']:.2f}MB")
            print(f"    内存增长: {self.memory_results['memory_growth_mb']:.2f}MB")
            print(f"    增长率: {self.memory_results['growth_rate']:.2f}%")
            print(f"    峰值内存: {self.memory_results['peak_memory_mb']:.2f}MB")
            verdict = self.memory_results.get("verdict", "N/A")
            print(f"    评估: {verdict}")

        print("\n" + "-" * 70)
        print("  3. 异常输入测试结果")
        print("-" * 70)
        for test_name, result in self.abnormal_results.items():
            status = "PASS" if result["pass"] else "FAIL"
            print(f"    [{status}] {test_name}")
            print(f"           状态码: {result.get('status_code', 'N/A')}, 说明: {result.get('detail', '')}")

        print("\n" + "-" * 70)
        print("  4. 总体评估")
        print("-" * 70)
        overall = self._overall_assessment()
        print(f"    并发测试: {overall['concurrent']}")
        print(f"    内存测试: {overall['memory']}")
        print(f"    异常输入测试: {overall['abnormal']}")
        print(f"    综合评级: {overall['overall']}")
        print("=" * 70)

    def _overall_assessment(self):
        result = {"concurrent": "N/A", "memory": "N/A", "abnormal": "N/A", "overall": "N/A"}

        if self.concurrent_results:
            rates = [r.get("success_rate", 0) for r in self.concurrent_results.values() if "error" not in r]
            if rates:
                avg_rate = statistics.mean(rates)
                if avg_rate >= 99:
                    result["concurrent"] = "优秀 (成功率≥99%)"
                elif avg_rate >= 95:
                    result["concurrent"] = "良好 (成功率≥95%)"
                elif avg_rate >= 90:
                    result["concurrent"] = "一般 (成功率≥90%)"
                else:
                    result["concurrent"] = "较差 (成功率<90%)"

        if self.memory_results and "error" not in self.memory_results:
            growth = self.memory_results.get("growth_rate", 0)
            if growth < 10:
                result["memory"] = "优秀 (增长率<10%)"
            elif growth < 30:
                result["memory"] = "良好 (增长率<30%)"
            elif growth < 50:
                result["memory"] = "一般 (增长率<50%)"
            else:
                result["memory"] = "较差 (增长率≥50%)"

        if self.abnormal_results:
            pass_count = sum(1 for r in self.abnormal_results.values() if r["pass"])
            total = len(self.abnormal_results)
            ratio = pass_count / total if total > 0 else 0
            if ratio >= 1.0:
                result["abnormal"] = f"优秀 ({pass_count}/{total}通过)"
            elif ratio >= 0.8:
                result["abnormal"] = f"良好 ({pass_count}/{total}通过)"
            elif ratio >= 0.6:
                result["abnormal"] = f"一般 ({pass_count}/{total}通过)"
            else:
                result["abnormal"] = f"较差 ({pass_count}/{total}通过)"

        scores = []
        for key in ["concurrent", "memory", "abnormal"]:
            val = result[key]
            if "优秀" in val:
                scores.append(4)
            elif "良好" in val:
                scores.append(3)
            elif "一般" in val:
                scores.append(2)
            elif "较差" in val:
                scores.append(1)
        if scores:
            avg = statistics.mean(scores)
            if avg >= 3.5:
                result["overall"] = "优秀"
            elif avg >= 2.5:
                result["overall"] = "良好"
            elif avg >= 1.5:
                result["overall"] = "一般"
            else:
                result["overall"] = "较差"

        return result


def check_server(host):
    try:
        url = f"{host}/"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def _make_headers(token):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def _single_request_httpx(client, url, headers, method="GET", data=None):
    start = time.monotonic()
    try:
        if method == "GET":
            resp = await client.get(url, headers=headers)
        else:
            resp = await client.post(url, headers=headers, json=data)
        elapsed = time.monotonic() - start
        return {"status": resp.status_code, "time": elapsed, "error": None}
    except Exception as e:
        elapsed = time.monotonic() - start
        return {"status": None, "time": elapsed, "error": str(e)}


async def _single_request_aiohttp(session, url, headers, method="GET", data=None):
    start = time.monotonic()
    try:
        if method == "GET":
            async with session.get(url, headers=headers) as resp:
                await resp.read()
                elapsed = time.monotonic() - start
                return {"status": resp.status, "time": elapsed, "error": None}
        else:
            async with session.post(url, headers=headers, json=data) as resp:
                await resp.read()
                elapsed = time.monotonic() - start
                return {"status": resp.status, "time": elapsed, "error": None}
    except Exception as e:
        elapsed = time.monotonic() - start
        return {"status": None, "time": elapsed, "error": str(e)}


async def _concurrent_fallback(url, headers, n):
    def sync_request():
        start = time.monotonic()
        try:
            req = urllib.request.Request(url, method="GET")
            for key, val in headers.items():
                req.add_header(key, val)
            with urllib.request.urlopen(req, timeout=30) as resp:
                elapsed = time.monotonic() - start
                return {"status": resp.status, "time": elapsed, "error": None}
        except Exception as e:
            elapsed = time.monotonic() - start
            return {"status": None, "time": elapsed, "error": str(e)}

    loop = asyncio.get_event_loop()
    tasks = [loop.run_in_executor(None, sync_request) for _ in range(n)]
    return await asyncio.gather(*tasks)


async def concurrent_test(host, token, concurrency_levels, endpoint="/"):
    results = {}
    url = f"{host}{endpoint}"
    headers = _make_headers(token)

    for n in concurrency_levels:
        print(f"  正在测试并发数 {n} ...", end=" ", flush=True)
        tasks_results = []

        if HAS_HTTPX:
            async with httpx.AsyncClient(timeout=30.0) as client:
                tasks = [_single_request_httpx(client, url, headers) for _ in range(n)]
                tasks_results = await asyncio.gather(*tasks)
        elif HAS_AIOHTTP:
            async with aiohttp.ClientSession() as session:
                tasks = [_single_request_aiohttp(session, url, headers) for _ in range(n)]
                tasks_results = await asyncio.gather(*tasks)
        else:
            tasks_results = await _concurrent_fallback(url, headers, n)

        if not tasks_results:
            results[n] = {"error": "无可用的异步HTTP客户端 (请安装 httpx 或 aiohttp)"}
            print("失败")
            continue

        times = [r["time"] for r in tasks_results]
        success_count = sum(1 for r in tasks_results if r["status"] and 200 <= r["status"] < 500)
        fail_count = sum(1 for r in tasks_results if r["error"] is not None)
        errors = [r["error"] for r in tasks_results if r["error"]]

        results[n] = {
            "total_requests": n,
            "success_count": success_count,
            "fail_count": fail_count,
            "success_rate": (success_count / n) * 100 if n > 0 else 0,
            "avg_time": statistics.mean(times) if times else 0,
            "min_time": min(times) if times else 0,
            "max_time": max(times) if times else 0,
            "median_time": statistics.median(times) if times else 0,
            "errors": errors,
        }
        print(f"完成 (成功率: {results[n]['success_rate']:.1f}%)")

    return results


def _get_process_memory():
    if HAS_PSUTIL:
        proc = psutil.Process()
        return proc.memory_info().rss / (1024 * 1024)
    return None


def memory_test(host, token, num_requests=1000, endpoint="/api/chat"):
    url = f"{host}{endpoint}"
    headers = _make_headers(token)

    tracemalloc.start()
    initial_tracemalloc = tracemalloc.get_traced_memory()[0] / (1024 * 1024)
    initial_psutil = _get_process_memory()

    chat_payload = {"message": "你好", "character_id": None, "model": None}

    memory_samples = []
    success_count = 0
    error_count = 0

    print(f"  正在发送 {num_requests} 次顺序请求到 {endpoint} ...")

    for i in range(num_requests):
        try:
            data = json.dumps(chat_payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, method="POST")
            for key, val in headers.items():
                req.add_header(key, val)
            with urllib.request.urlopen(req, timeout=60) as resp:
                if resp.status == 200:
                    success_count += 1
                else:
                    error_count += 1
        except urllib.error.HTTPError as e:
            if e.code in (400, 401, 403, 422):
                success_count += 1
            else:
                error_count += 1
        except Exception:
            error_count += 1

        if (i + 1) % 100 == 0:
            current_psutil = _get_process_memory()
            current_tracemalloc = tracemalloc.get_traced_memory()[0] / (1024 * 1024)
            sample = {"request_num": i + 1, "tracemalloc_mb": current_tracemalloc}
            if current_psutil is not None:
                sample["psutil_mb"] = current_psutil
            memory_samples.append(sample)
            print(f"    已完成 {i + 1}/{num_requests} 请求", flush=True)

    final_tracemalloc = tracemalloc.get_traced_memory()[0] / (1024 * 1024)
    peak_tracemalloc = tracemalloc.get_traced_memory()[1] / (1024 * 1024)
    final_psutil = _get_process_memory()
    tracemalloc.stop()

    memory_growth = final_tracemalloc - initial_tracemalloc
    growth_rate = (memory_growth / initial_tracemalloc * 100) if initial_tracemalloc > 0 else 0

    if growth_rate < 10:
        verdict = "无明显内存泄漏"
    elif growth_rate < 30:
        verdict = "轻微内存增长，需关注"
    elif growth_rate < 50:
        verdict = "存在内存增长，建议排查"
    else:
        verdict = "疑似内存泄漏，需紧急排查"

    result = {
        "total_requests": num_requests,
        "success_count": success_count,
        "error_count": error_count,
        "initial_memory_mb": initial_tracemalloc,
        "final_memory_mb": final_tracemalloc,
        "peak_memory_mb": peak_tracemalloc,
        "memory_growth_mb": memory_growth,
        "growth_rate": growth_rate,
        "verdict": verdict,
        "samples": memory_samples,
    }

    if initial_psutil is not None and final_psutil is not None:
        result["psutil_initial_mb"] = initial_psutil
        result["psutil_final_mb"] = final_psutil
        result["psutil_growth_mb"] = final_psutil - initial_psutil

    return result


def _send_chat_request(url, headers, payload):
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        for key, val in headers.items():
            req.add_header(key, val)
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return {"status_code": resp.status, "body": body, "error": None}
    except urllib.error.HTTPError as e:
        body = None
        try:
            body = json.loads(e.read().decode("utf-8"))
        except Exception:
            pass
        return {"status_code": e.code, "body": body, "error": str(e)}
    except Exception as e:
        return {"status_code": None, "body": None, "error": str(e)}


def _extract_detail(res):
    if res["error"] and res["status_code"] is None:
        return f"连接错误: {res['error'][:80]}"
    if res["body"] and isinstance(res["body"], dict):
        detail = res["body"].get("detail", "")
        if isinstance(detail, str):
            return detail[:80]
        return str(detail)[:80]
    if res["status_code"]:
        return f"HTTP {res['status_code']}"
    return "未知错误"


def abnormal_input_test(host, token, endpoint="/api/chat"):
    url = f"{host}{endpoint}"
    headers = _make_headers(token)
    results = {}

    long_text = "A" * 10000
    res = _send_chat_request(url, headers, {"message": long_text})
    results["超长文本(10000字符)"] = {
        "pass": res["status_code"] is not None and res["status_code"] < 500,
        "status_code": res["status_code"],
        "detail": _extract_detail(res),
    }

    sql_injections = [
        "' OR 1=1 --",
        "'; DROP TABLE users; --",
        "\" UNION SELECT * FROM passwords --",
    ]
    for idx, payload in enumerate(sql_injections):
        res = _send_chat_request(url, headers, {"message": payload})
        test_name = f"SQL注入尝试#{idx+1}"
        results[test_name] = {
            "pass": res["status_code"] is not None and res["status_code"] < 500,
            "status_code": res["status_code"],
            "detail": _extract_detail(res),
        }

    xss_payloads = [
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert(1)>",
        "javascript:alert(document.cookie)",
    ]
    for idx, payload in enumerate(xss_payloads):
        res = _send_chat_request(url, headers, {"message": payload})
        test_name = f"XSS尝试#{idx+1}"
        results[test_name] = {
            "pass": res["status_code"] is not None and res["status_code"] < 500,
            "status_code": res["status_code"],
            "detail": _extract_detail(res),
        }

    res = _send_chat_request(url, headers, {"message": ""})
    results["空输入"] = {
        "pass": res["status_code"] is not None and res["status_code"] in (400, 422),
        "status_code": res["status_code"],
        "detail": _extract_detail(res),
    }

    res = _send_chat_request(url, headers, {"message": None})
    results["null值消息"] = {
        "pass": res["status_code"] is not None and res["status_code"] in (400, 422),
        "status_code": res["status_code"],
        "detail": _extract_detail(res),
    }

    long_conv_id = "C" * 10000
    res = _send_chat_request(url, headers, {"message": "test", "character_id": long_conv_id})
    results["超长角色ID(10000字符)"] = {
        "pass": res["status_code"] is not None and res["status_code"] < 500,
        "status_code": res["status_code"],
        "detail": _extract_detail(res),
    }

    res = _send_chat_request(url, headers, {})
    results["缺失message字段"] = {
        "pass": res["status_code"] is not None and res["status_code"] in (400, 422),
        "status_code": res["status_code"],
        "detail": _extract_detail(res),
    }

    res = _send_chat_request(url, headers, {"message": "test", "temperature": "invalid"})
    results["无效temperature类型"] = {
        "pass": res["status_code"] is not None and res["status_code"] in (400, 422),
        "status_code": res["status_code"],
        "detail": _extract_detail(res),
    }

    return results


def main():
    parser = argparse.ArgumentParser(description="三月七语音对话系统 - 压力测试")
    parser.add_argument("--host", default="http://localhost:8000", help="API服务器地址")
    parser.add_argument("--token", default="", help="认证Token")
    parser.add_argument("--memory-requests", type=int, default=1000, help="内存测试请求数")
    parser.add_argument("--output", default="", help="报告输出文件路径(JSON)")
    parser.add_argument("--skip-memory", action="store_true", help="跳过内存测试")
    args = parser.parse_args()

    host = args.host.rstrip("/")
    token = args.token

    print("=" * 70)
    print("  三月七语音对话系统 - 压力测试")
    print("=" * 70)
    print(f"  目标服务器: {host}")
    print(f"  Token: {'(已提供)' if token else '(未提供)'}")
    print(f"  httpx: {'可用' if HAS_HTTPX else '不可用'}")
    print(f"  aiohttp: {'可用' if HAS_AIOHTTP else '不可用'}")
    print(f"  psutil: {'可用' if HAS_PSUTIL else '不可用'}")
    print()

    print("正在检查服务器连接...", end=" ", flush=True)
    if not check_server(host):
        print("失败")
        print(f"\n错误: 无法连接到服务器 {host}")
        print("请确保服务器正在运行，然后重试。")
        sys.exit(1)
    print("成功")

    report = StressTestReport()

    print("\n[1/3] 并发访问测试")
    print("-" * 40)
    report.concurrent_results = asyncio.run(concurrent_test(host, token, [10, 50, 100]))

    if not args.skip_memory:
        print("\n[2/3] 内存泄漏测试")
        print("-" * 40)
        report.memory_results = memory_test(host, token, num_requests=args.memory_requests)
    else:
        print("\n[2/3] 内存泄漏测试 - 已跳过")
        report.memory_results = {"error": "已跳过"}

    print("\n[3/3] 异常输入测试")
    print("-" * 40)
    report.abnormal_results = abnormal_input_test(host, token)

    report.print_report()

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
        print(f"\n报告已保存到: {args.output}")


if __name__ == "__main__":
    main()
