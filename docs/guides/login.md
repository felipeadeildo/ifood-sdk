# Login

The web client has no password login. The account is identified, then a one-time code
arrives by WhatsApp. The code expires in 60 seconds and the key behind it works once.

```python
import ifood

pending = ifood.login("+55 11 90000-0000")   # writes nothing yet
client = pending.verify("123456")            # returns the client, saves the session
```

`login` accepts `+55 11 90000-0000`, `(11) 90000-0000` or `5582900000000`. Pass
`email=` when the account has one, and `store=` to change where the session is saved.

Next run, the session is already on disk:

```python
client = ifood.connect()
```

`connect` raises `NotLoggedIn` when there is nothing saved, and the message says to call
`ifood.login` first.

`start_otp` returns a challenge object. Keep it in memory: the code is only accepted with
that key, and a failure after the exchange costs a new code.

The last step requires an e-mail, even when the code arrives by phone. Pass it as
`email=` when the account has one, or store the identifier from `/v4/identity-providers`.

Unknown: the e-mail delivery shape. Attempts with `type: EMAIL` returned 400, so the SDK
refuses instead of guessing.
