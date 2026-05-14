package main

const (
	CodeTypeOK              uint32 = 0
	CodeTypeInvalidTxFormat uint32 = 2
	AppVersion              uint64 = 1
	TransferType            string = "transfer"
	AddValidatorType        string = "addval"
	RemoveValidatorType     string = "remval"
	UpdateValidatorType     string = "updval"
	StatusCompleted         string = "Completed"
	StatusFailed            string = "Failed"
	StatusOnGoing           string = "OnGoing"
	StatusExpired           string = "Expired"
)
