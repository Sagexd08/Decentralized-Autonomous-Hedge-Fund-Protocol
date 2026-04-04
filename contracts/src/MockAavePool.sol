pragma solidity ^0.8.20;

interface IERC20Transfer {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function transfer(address to, uint256 amount) external returns (bool);
}

interface IMockERC20Mint {
    function mint(address to, uint256 amount) external;
}

contract MockAavePool {

    mapping(address => mapping(address => uint256)) public supplyPositions;

    mapping(address => mapping(address => uint256)) public debtPositions;

    address[] private _users;
    address[] private _tokens;
    mapping(address => bool) private _knownUser;
    mapping(address => bool) private _knownToken;

    uint256 public constant SUPPLY_RATE_PER_TICK_NUM = 5;
    uint256 public constant SUPPLY_RATE_PER_TICK_DEN = 100 * 365 * 24 * 360;

    uint256 public constant BORROW_RATE_PER_TICK_NUM = 8;
    uint256 public constant BORROW_RATE_PER_TICK_DEN = 100 * 365 * 24 * 360;

    event Supplied(address indexed user, address indexed token, uint256 amount);
    event Borrowed(address indexed user, address indexed token, uint256 amount);
    event Withdrawn(address indexed user, address indexed token, uint256 amount);
    event InterestAccrued();

    function supply(address token, uint256 amount, address onBehalfOf) external {
        require(amount > 0, "Amount must be > 0");
        IERC20Transfer(token).transferFrom(msg.sender, address(this), amount);
        supplyPositions[onBehalfOf][token] += amount;
        _trackUser(onBehalfOf);
        _trackToken(token);
        emit Supplied(onBehalfOf, token, amount);
    }

    function borrow(address token, uint256 amount, address onBehalfOf) external {
        require(amount > 0, "Amount must be > 0");
        IMockERC20Mint(token).mint(onBehalfOf, amount);
        debtPositions[onBehalfOf][token] += amount;
        _trackUser(onBehalfOf);
        _trackToken(token);
        emit Borrowed(onBehalfOf, token, amount);
    }

    function withdraw(address token, uint256 amount, address to) external {
        require(supplyPositions[msg.sender][token] >= amount, "Insufficient supply position");
        supplyPositions[msg.sender][token] -= amount;
        IERC20Transfer(token).transfer(to, amount);
        emit Withdrawn(msg.sender, token, amount);
    }

    function accrueInterest() external {
        for (uint256 u = 0; u < _users.length; u++) {
            address user = _users[u];
            for (uint256 t = 0; t < _tokens.length; t++) {
                address token = _tokens[t];
                uint256 supplyAmt = supplyPositions[user][token];
                if (supplyAmt > 0) {
                    uint256 interest = supplyAmt * SUPPLY_RATE_PER_TICK_NUM / SUPPLY_RATE_PER_TICK_DEN;
                    supplyPositions[user][token] += interest;
                }
                uint256 debt = debtPositions[user][token];
                if (debt > 0) {
                    uint256 interest = debt * BORROW_RATE_PER_TICK_NUM / BORROW_RATE_PER_TICK_DEN;
                    debtPositions[user][token] += interest;
                }
            }
        }
        emit InterestAccrued();
    }

    function _trackUser(address user) internal {
        if (!_knownUser[user]) {
            _knownUser[user] = true;
            _users.push(user);
        }
    }

    function _trackToken(address token) internal {
        if (!_knownToken[token]) {
            _knownToken[token] = true;
            _tokens.push(token);
        }
    }
}
