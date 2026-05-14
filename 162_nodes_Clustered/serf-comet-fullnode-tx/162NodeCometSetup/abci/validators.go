package main

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"github.com/cometbft/cometbft/abci/types"
	cryptoenc "github.com/cometbft/cometbft/crypto/encoding"
	"sort"
)

// add, update, or remove a validator.
func (app *MyApp) UpdateValidator(vReqTx string) {
	var vtx Validators
	if err := json.Unmarshal([]byte(vReqTx), &vtx); err != nil {
		app.Logger.Error(fmt.Sprintf("Error unmarshalling validator tx json: %v", err))
		return
	}
	tp := vtx.Type
	for _, val := range vtx.Validator {
		pubKeyBytes, err := base64.StdEncoding.DecodeString(val.PubKeyBytes)
		if err != nil {
			app.Logger.Error("PubKey decode error:", "err", err)
			continue
		}
		pubkey, err := cryptoenc.PubKeyFromTypeAndBytes(val.PubKeyType, pubKeyBytes)
		if err != nil {
			app.Logger.Error("PubKey Error:", "err", err)
		}
		addr := string(pubkey.Address())
		switch tp {
		case RemoveValidatorType:
			removeUpdate := types.ValidatorUpdate{
				PubKeyType:  val.PubKeyType,
				PubKeyBytes: pubKeyBytes,
				Power:       0,
			}
			if _, ok := app.ValAddrToPubKeyMap[addr]; !ok {
				app.Logger.Error("Attempt to remove non-existent validator", "addr", addr)
				continue
			}
			app.AppendValidatorUpdateOnce(addr, removeUpdate)
			app.RemoveFromStateValidator(addr)
			delete(app.ValAddrToPubKeyMap, addr)

		case AddValidatorType, UpdateValidatorType:
			app.ValAddrToPubKeyMap[addr] = pubkey
			app.AddOrUpdateStateValidator(types.ValidatorUpdate{
				PubKeyType:  val.PubKeyType,
				PubKeyBytes: pubKeyBytes,
				Power:       val.Power,
			}, addr)
			app.AppendValidatorUpdateOnce(addr, types.ValidatorUpdate{
				PubKeyType:  val.PubKeyType,
				PubKeyBytes: pubKeyBytes,
				Power:       val.Power,
			})

		default:
			app.Logger.Error(fmt.Sprintf("Unknown validator update type: %s", tp))
			return
		}
	}
	app.SortStateValidatorByAddress()
}

func (app *MyApp) AddOrUpdateStateValidator(v types.ValidatorUpdate, addr string) {
	// update if exists
	for i, existing := range app.State.Validator {
		pub, _ := cryptoenc.PubKeyFromTypeAndBytes(existing.PubKeyType, existing.PubKeyBytes)
		if string(pub.Address()) == addr {
			app.State.Validator[i] = v
			return
		}
	}
	app.State.Validator = append(app.State.Validator, v)
}

func (app *MyApp) RemoveFromStateValidator(addr string) {
	newList := make([]types.ValidatorUpdate, 0, len(app.State.Validator))
	for _, existing := range app.State.Validator {
		pub, _ := cryptoenc.PubKeyFromTypeAndBytes(existing.PubKeyType, existing.PubKeyBytes)
		if string(pub.Address()) != addr {
			newList = append(newList, existing)
		}
	}
	app.State.Validator = newList
}

func (app *MyApp) SortStateValidatorByAddress() {
	sort.Slice(app.State.Validator, func(i, j int) bool {
		pub1, _ := cryptoenc.PubKeyFromTypeAndBytes(app.State.Validator[i].PubKeyType, app.State.Validator[i].PubKeyBytes)
		pub2, _ := cryptoenc.PubKeyFromTypeAndBytes(app.State.Validator[j].PubKeyType, app.State.Validator[j].PubKeyBytes)

		return string(pub1.Address()) < string(pub2.Address())
	})
}

func (app *MyApp) CheckValidatorTX(reqtx string) (*types.CheckTxResponse, error) {
	var tx Validators
	if err := json.Unmarshal([]byte(reqtx), &tx); err != nil {
		msg := fmt.Sprintf("ERROR: Failed to parse JSON: %v", err)
		return &types.CheckTxResponse{Code: 2, Log: msg}, nil
	}
	if len(tx.Validator) == 0 {
		logMsg := "ABCI CheckTx ERROR: Missing one or more required fields (type, Validator)."
		app.Logger.Error(logMsg)
		return &types.CheckTxResponse{Code: 4, Log: logMsg}, nil
	}
	for _, v := range tx.Validator {
		if v.Power < 0 {
			return &types.CheckTxResponse{Code: 5, Log: "Validator power cannot be negative"}, nil
		}
	}

	app.Logger.Info(fmt.Sprintf("Validator Transaction OK."))
	return &types.CheckTxResponse{Code: CodeTypeOK, Log: "Validator Transaction Check passed."}, nil
}

func (app *MyApp) AppendValidatorUpdateOnce(addr string, vu types.ValidatorUpdate) {
	if _, seen := app.UpdatedValidatorsThisBlock[addr]; seen {
		app.Logger.Info("Skipping duplicate validator update in same block", "addr", addr)
		return
	}
	app.UpdatedValidatorsThisBlock[addr] = struct{}{}
	app.ValUpdates = append(app.ValUpdates, vu)
}

func (app *MyApp) punishValidators(req *types.FinalizeBlockRequest) {
	app.ValUpdates = make([]types.ValidatorUpdate, 0)
	app.UpdatedValidatorsThisBlock = make(map[string]struct{})

	//Punish Validators committing equivocation
	for _, ev := range req.Misbehavior {
		if ev.Type == types.MISBEHAVIOR_TYPE_DUPLICATE_VOTE {
			addr := string(ev.Validator.Address)
			pubKey, ok := app.ValAddrToPubKeyMap[addr]
			if !ok {
				app.Logger.Error(fmt.Sprintf("Address %q should be punished but address not found", addr))
				continue
			}
			power := ev.Validator.Power - 2
			if power < 0 {
				power = 0
			}
			update := types.ValidatorUpdate{
				Power:       power,
				PubKeyType:  pubKey.Type(),
				PubKeyBytes: pubKey.Bytes(),
			}
			app.AppendValidatorUpdateOnce(addr, update)

			if power == 0 {
				app.RemoveFromStateValidator(addr)
			} else {
				app.AddOrUpdateStateValidator(types.ValidatorUpdate{
					Power:       power,
					PubKeyType:  pubKey.Type(),
					PubKeyBytes: pubKey.Bytes(),
				}, addr)
			}
			app.Logger.Info("Decreased validator power by 2 because of the equivocation", "val", addr)
		}
	}
}
