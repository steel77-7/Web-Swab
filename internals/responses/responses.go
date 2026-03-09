package response

import (
	"github.com/gin-gonic/gin"
	"github.com/steel77-7/Web-Swab/internals/types"
)

func Success(c *gin.Context, code int, data interface{}) {
	c.JSON(code, types.APIResponse{
		Success: true,
		Code:    code,
		Data:    data,
	})
}

func Fail(c *gin.Context, code int, err string) {
	c.JSON(code, types.APIResponse{
		Success: false,
		Code:    code,
		Error:   err,
	})
}
