# Disclaimer

This project is not affiliated with iFood.

`ifood-sdk` is an independent client, written by reverse engineering the public web
client and by measuring the API with a real account. It is not endorsed by, sponsored by,
or supported by iFood. iFood and its marks belong to their owners.

## What this project is for

Study, interoperability and personal automation on your own account. The code exists to
show how the flows work and to let a person ask their own agent to repeat an order they
already placed.

## What it does not do

- It does not bypass authentication. You log in with your own phone number and the
  one-time code iFood sends you.
- It does not create accounts, scrape at scale, resell data, or hide who is calling.
- It does not work around the platform's protections. Where the edge blocks a request,
  the client reports `EdgeBlocked` and stops.

## Your responsibilities

- Follow the iFood Terms of Service and any applicable law in your country.
- Keep the request rate low. The project does not add retry storms or parallel floods.
- Use it on an account you own. Do not point it at other people's accounts.
- Expect breakage. The API is unofficial and changes without notice.

## No warranty

The software is provided as is, under the MIT license, without warranty of any kind. The
authors are not liable for account restrictions, lost orders, charges, or any other
damage that results from using it. If you run it, the risk is yours.
