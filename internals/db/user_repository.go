package db

import (
	"database/sql"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/steel77-7/Web-Swab/internals/types"
)

type UserRepository struct {
	Pool *pgxpool.Pool
}

func (u *UserRepository) VerifyUser(user types.User) bool {
	//verify the user first using the user id and the api key
	q := `SELECT user_id , api_key FROM users WHERE user_id = $1 AND api_key = $2`
	//use some kind of signing function for this too ig
	//but for now just simple
	var stored_user types.User
	row := u.Pool.QueryRow(CTX, q, user.ID, user.APIKey)
	err := row.Scan(&stored_user.ID, &stored_user.APIKey)
	if err == sql.ErrNoRows {
		return false
	}
	return true
}
