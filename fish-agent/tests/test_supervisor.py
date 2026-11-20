import asyncio
import unittest

from agents.supervisor import classify_complexity, supervisor_graph
from agents.worker_lifecycle import WorkerRegistry


class SupervisorTests(unittest.IsolatedAsyncioTestCase):
    async def test_simple_task_runs_one_worker(self):
        result = await supervisor_graph.ainvoke(
            {"task": "Проверь цену горбуши", "intent": "price_query", "params": {}}
        )

        self.assertEqual(result["complexity"], "simple")
        self.assertEqual(len(result["worker_results"]), 1)
        self.assertEqual(result["worker_results"][0]["worker"], "pricing")

    async def test_multi_domain_task_runs_multiple_workers(self):
        result = await supervisor_graph.ainvoke(
            {
                "task": "Проверь цену трески и создай заказ",
                "intent": "create_order",
                "params": {},
            }
        )

        self.assertEqual(result["complexity"], "complex")
        self.assertEqual(
            [item["worker"] for item in result["worker_results"]],
            ["pricing", "order"],
        )

    async def test_stop_all_cancels_workers_and_rejects_new_work(self):
        registry = WorkerRegistry()
        started = asyncio.Event()

        async def worker():
            async with registry.running():
                started.set()
                await asyncio.Event().wait()

        task = asyncio.create_task(worker())
        await started.wait()
        await registry.stop_all()

        self.assertTrue(task.cancelled())
        self.assertTrue(registry.stopped)
        with self.assertRaises(RuntimeError):
            async with registry.running():
                pass

    def test_complexity_is_derived_from_detected_domains(self):
        self.assertEqual(classify_complexity("Напиши пост", "create_post"), "simple")
        self.assertEqual(
            classify_complexity("Проверь цену и создай заказ", "create_order"),
            "complex",
        )
