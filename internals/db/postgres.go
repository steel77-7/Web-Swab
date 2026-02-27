// here the connection to the db will be made and the pub sub will be made here
package internals

import "context"

func main() {
	conn, err := pgx.Connect(context.Background())
}
