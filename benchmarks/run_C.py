"""Independent C entry; delegates to the frozen toolkit."""
import sys
from benchmark import main

if __name__ == "__main__":
    sys.argv.insert(1, "C")
    sys.exit(main())
