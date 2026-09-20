(function AuthErrorInterceptor() {
	/**
	 * Global flag: true when an auth endpoint responded with a 400 HTTP status error
	 * @type {boolean}
	 */
	window.__authError = false;

	/**
	 * Checks whether an URL contains a login or password-reset endpoint.
	 * @param {unknown} [url] - The requested URL.
	 * @returns {boolean} returns true if the url is a string containing /auth/login or /auth/reset.
	 */
	function isAuthUrl(url) {
		return (
			typeof url === "string" &&
			(url.includes("/auth/login") || url.includes("/auth/reset"))
		);
	}

	/**
	 * Checks whether a response body is a captcha challenge
	 * @param {string} [text] - The response body as plain text.
	 * @returns {boolean} returns true if the body contains a known captcha key.
	 */
	function isCaptchaResponse(text) {
		if (!text) return false;
		return (
			text.includes("captcha_key") ||
			text.includes("captcha_sitekey") ||
			text.includes("captcha_service")
		);
	}

	// Patch XMLHttpRequest.prototype.open to observe auth responses.
	// Sets window.__authError to true if the HTTP status code is 400 and the response is not a captcha challenge.
	const originalOpen = XMLHttpRequest.prototype.open;
	XMLHttpRequest.prototype.open = function (method, url, ...rest) {
		if (isAuthUrl(url)) {
			this.addEventListener("load", () => {
				if (
					this.status === 400 &&
					!isCaptchaResponse(this.responseText)
				) {
					window.__authError = true;
				}
			});
		}
		return originalOpen.call(this, method, url, ...rest);
	};
})();
