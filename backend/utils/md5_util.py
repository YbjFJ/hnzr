import hashlib

class Md5Util:
    # 默认字符集（与Java保持一致）
    DEFAULT_CHARSET = 'UTF-8'

    # 十六进制字符映射表（与Java保持一致）
    hexDigits = '0123456789abcdef'

    @classmethod
    def get_md5_string(cls, input_str: str) -> str:
        """
        生成字符串的MD5校验值
        """
        # 将字符串编码为字节（默认使用UTF-8）
        byte_input = input_str.encode(cls.DEFAULT_CHARSET)
        return cls._get_md5_bytes(byte_input)

    @classmethod
    def check_password(cls, password: str, md5_pwd_str: str) -> bool:
        """
        验证密码的MD5校验值是否匹配
        """
        return cls.get_md5_string(password) == md5_pwd_str

    @classmethod
    def _get_md5_bytes(cls, byte_input: bytes) -> str:
        """
        生成字节数组的MD5校验值
        """
        # 创建MD5哈希对象
        md5_hash = hashlib.md5()

        # 更新哈希对象（支持多次update）
        md5_hash.update(byte_input)

        # 生成十六进制字符串（与Java实现保持一致）
        return cls._bytes_to_hex(md5_hash.digest())

    @classmethod
    def _bytes_to_hex(cls, byte_data: bytes) -> str:
        """
        将字节数组转换为十六进制字符串
        """
        hex_str = ""
        for byte in byte_data:
            # 取高4位
            high_nibble = (byte >> 4) & 0x0F
            # 取低4位
            low_nibble = byte & 0x0F
            hex_str += cls.hexDigits[high_nibble] + cls.hexDigits[low_nibble]
        return hex_str
