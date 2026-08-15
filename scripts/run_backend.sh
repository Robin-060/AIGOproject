#!/bin/bash

python3 -m uvicorn src.demo_backend.app:app --host 0.0.0.0 --port 8000
