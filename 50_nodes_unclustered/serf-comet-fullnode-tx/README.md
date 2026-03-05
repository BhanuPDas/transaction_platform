# Source Code And Configurations for Transaction Module
This repository has code changes and CometBFT configurations for a 50 Node Topology. This includes scripts to automate the process.

## Steps to set up CometBFT

1. Pull the repository to the local system (VM).
2. Navigate to the folder 25NodeCometSetup ***cd 25NodeCometSetup***
3. Execute the script setup_cometbft ***./setup_cometbft.sh***
4. The script installs all required software and starts all applications required for the transaction module. The script uses the config file and deploys the application code provided in the folder.
5. To test transactions, go to the root folder on the specific containers and run the python file - main.py ***python3 main.py***
6. To trigger transactions from UI on a VM, run tx_api.py. This will expose an API for UI to send a request to initiate a transaction. Make sure to terminate the main.py script if running before running tx_api.py. ***python3 tx_api.py***
7. If the ABCI client or CometBFT is down or not responding, in either case, run the reset_comet script. It will automatically restart the application. ***./reset_comet.sh***

## Steps to set up Validators
ABCI enables CometBFT to add validators dynamically, without hardcoding it in genesis file. In order to update validators follow below steps:

1. Adding/Updating/Removing validators needs no special set up in CometBFT, it has to be passed as a regular transaction and ABCI will handle it internally.
2. Run validator_tx file. ***python3 validator_tx.py***
3. This will start an API which accepts request with validator details. 
4. Using curl on terminal, send a ***POST*** request in the below format.
```text
URL: http://<container Name/IP>:5010/validatorTx
```
```bash
curl -X POST http://localhost:5010/validatorTx   -H "Content-Type: application/json"   -d '{
  "type": "addval",
  "validator": [
    {
      "power": 50,
      "pub_key_bytes": "xxxx",
      "pub_key_type": "ed25519"
    },
    {
      "power": 50,
      "pub_key_bytes": "xxxx",
      "pub_key_type": "ed25519"
    },
    {
      "power": 50,
      "pub_key_bytes": "xxxx",
      "pub_key_type": "ed25519"
    },
    {
      "power": 50,
      "pub_key_bytes": "xxxx",
      "pub_key_type": "ed25519"
    }
  ]
}'
```
5. The type can be: **addval** (To add new validator/s), **updval** (To update existing validator/s) or **remval** (To remove existing validator/s)
6. To remove a validator, send power as 0 (-ve value is not allowed). 
7. Make sure to achieve a successful consensus, a minimum of **3f+1** number of validators are always maintained. Else consensus will fail.
8. The API will then construct the payload as per CometBFT standard and send the transaction to CometBFT.
9. Validators are then updated by CometBFT.
10. [Optional] You may terminate the API once validators are added.

***Note: [Important]*** Make sure CometBFT peers are already connected before initiating validators transaction. 
In other words, first dial_peers then add/remove validators else CometBFT will panic and fail. So follow the below sequence:
1. First run main.py (This script automatically dial peers on first run)
2. Run validator_tx.py to add validators.
3. Followed by regular transactions. (main.py)


```text
Note: The configuration/reset scripts are applicable for 50-node topology only. For other topology setups, these scripts need to be updated accordingly.
```