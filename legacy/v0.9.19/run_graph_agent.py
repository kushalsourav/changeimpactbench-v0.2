#!/usr/bin/env python3
"""CLI compatibility entry point for the single LangGraph runner."""
from benchmarks.runner import (EpisodeInterrupted, make_native_tools, build_graph,
    collect_graph_updates, run_episode, main)

if __name__ == '__main__':
    main()
