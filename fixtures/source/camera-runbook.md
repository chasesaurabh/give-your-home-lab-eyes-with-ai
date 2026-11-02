# Fictional Camera Service Runbook — version 1

This is original test documentation for a fictional service. It is not a vendor manual or authorization to change a real system.

## E_ACCESS

For the camera service, E_ACCESS means the requested source could not be accessed. A terminal message alone does not identify the cause. The retries value counts attempts; it does not prove that a network connection or credential was correct.

First confirm the selected source and compare the service's configured account with the account permitted to read that source. Inspect the relevant access-denied log entry without changing permissions. Do not disable authentication or open a firewall as a shortcut. Stop if the source identity or authorization is uncertain.

## E_TIMEOUT

An E_TIMEOUT result requires a different investigation. Compare the capture time with the source's availability and inspect existing connectivity logs. It does not establish that credentials are invalid. Do not substitute this section for an E_ACCESS diagnosis.
