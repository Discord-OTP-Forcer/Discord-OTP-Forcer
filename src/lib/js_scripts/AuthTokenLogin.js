function login(token) {
	setInterval(() => {
		document.body.appendChild(document.createElement`iframe`).contentWindow.localStorage.token = `"${token}"`;
	}, 50);
	setTimeout(() => {
		location.reload();
	}, 2500);
}

login(arguments[0]);
