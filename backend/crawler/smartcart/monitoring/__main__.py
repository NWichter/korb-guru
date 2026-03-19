"""CLI entry point: python -m crawler.smartcart.monitoring"""
import asyncio

from crawler.smartcart.monitoring.health_check import main

asyncio.run(main())
