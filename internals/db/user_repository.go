package db

import (
	"scraper/internals/types"

	"github.com/jackc/pgx/v5/pgxpool"
)

type UserRepository struct {
	Pool *pgxpool.Pool
}

func (u *UserRepository) VerifyUser(user types.User) {

}
