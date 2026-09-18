(function hardenWebStorage() {
	if (typeof window === "undefined") return;

	function lockProperty(obj, prop) {
		if (!obj) return;

		let desc;
		try {
			desc = Object.getOwnPropertyDescriptor(obj, prop);
		} catch {
			return;
		}

		if (!desc?.get) return;

		if (desc.configurable === false) return;

		try {
			Object.defineProperty(obj, prop, {
				get: desc.get,
				set: desc.set,
				enumerable: desc.enumerable,
				configurable: false,
			});
		} catch {
			// ignore
		}
	}

	try {
		lockProperty(window, "localStorage");
		lockProperty(window, "sessionStorage");
	} catch {
		// ignore
	}

	try {
		if (typeof Window !== "undefined" && Window.prototype) {
			lockProperty(Window.prototype, "localStorage");
			lockProperty(Window.prototype, "sessionStorage");
		}
	} catch {
		// ignore
	}
})();
